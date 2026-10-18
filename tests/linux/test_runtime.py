import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('runtime', Path(__file__).parents[2] / 'linux/extension/runtime.py')
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def extract(self, entries):
        archive = self.base / 'image.tar'
        with tarfile.open(archive, 'w') as tar:
            for name, kind, data in entries:
                item = tarfile.TarInfo(name)
                item.type = kind
                if kind == tarfile.REGTYPE:
                    encoded = data.encode()
                    item.size = len(encoded)
                    item.mode = 0o4755
                    tar.addfile(item, io.BytesIO(encoded))
                else:
                    item.linkname = data
                    tar.addfile(item)
        dest = self.base / 'root'
        dest.mkdir()
        runtime.safe_extract(archive, dest)
        return dest

    def test_normal_files_links_and_setuid_stripped(self):
        dest = self.extract([('image/usr/bin/bash', tarfile.REGTYPE, 'hello'),
                             ('image/bin', tarfile.SYMTYPE, 'usr/bin'),
                             ('image/usr/bin/sh', tarfile.LNKTYPE, 'image/usr/bin/bash')])
        self.assertEqual((dest / 'bin/bash').read_text(), 'hello')
        self.assertEqual((dest / 'usr/bin/sh').read_text(), 'hello')
        self.assertEqual((dest / 'usr/bin/bash').stat().st_mode & 0o7000, 0)

    def test_parent_traversal_rejected_before_strip(self):
        for name in ['../image/file', 'image/../file', '/image/file', 'image\\file']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                runtime.archive_path(name)

    def test_symlink_then_file_cannot_write_outside(self):
        outside = self.base / 'outside'
        outside.mkdir()
        with self.assertRaises((ValueError, FileExistsError)):
            self.extract([('image/escape', tarfile.SYMTYPE, str(outside)),
                          ('image/escape/payload', tarfile.REGTYPE, 'BAD')])
        self.assertFalse((outside / 'payload').exists())

    def test_hardlink_cannot_read_outside(self):
        with self.assertRaises(ValueError):
            self.extract([('image/key', tarfile.LNKTYPE, '/etc/passwd')])

    def test_hardlink_to_symlink_rejected(self):
        with self.assertRaises(ValueError):
            self.extract([('image/a', tarfile.SYMTYPE, '/etc/passwd'),
                          ('image/b', tarfile.LNKTYPE, 'image/a')])

    def test_device_nodes_skipped_only_under_dev(self):
        dest = self.extract([('image/dev/null', tarfile.CHRTYPE, '')])
        self.assertFalse((dest / 'dev/null').exists())

    def test_unexpected_device_node_rejected(self):
        with self.assertRaises(ValueError):
            self.extract([('image/etc/evil', tarfile.CHRTYPE, '')])

    def test_duplicate_files_rejected(self):
        with self.assertRaises(ValueError):
            self.extract([('image/a', tarfile.REGTYPE, 'one'), ('image/a', tarfile.REGTYPE, 'two')])

    def test_size_limit(self):
        previous = runtime.MAX_EXTRACTED
        runtime.MAX_EXTRACTED = 3
        try:
            with self.assertRaises(ValueError):
                self.extract([('image/a', tarfile.REGTYPE, 'four')])
        finally:
            runtime.MAX_EXTRACTED = previous

    def test_checksum_mismatch(self):
        file = self.base / 'image'
        file.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            runtime.verify_archive(file)

    def test_https_downgrade_rejected(self):
        with self.assertRaises(ValueError):
            runtime.HTTPSOnly().redirect_request(None, None, 302, '', {}, 'http://host/file')

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='linux space ')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.native = self.base / 'native'
        self.native.mkdir()
        for name in ('libproot.so', 'libproot-loader.so'):
            (self.native / name).touch()
        self.r = runtime.Runtime(self.base / 'files', self.native, self.base / 'workspace')
        (self.r.rootfs / 'usr/bin').mkdir(parents=True)
        (self.r.rootfs / 'usr/bin/bash').touch()

    def test_argv_preserves_unicode_spaces_and_metacharacters(self):
        command = ['printf', 'hello 世界\n$(touch stolen);\'"']
        args = self.r.argv(command)
        self.assertEqual(args[-2:], command)
        self.assertIn(str(self.r.workspace) + ':' + str(self.r.workspace), args)
        self.assertIn('--kill-on-exit', args)
        self.assertNotIn('/data/data/com.termux', ' '.join(args))

    def test_regular_user_runs_without_fake_root_and_gets_persistent_home(self):
        etc = self.r.rootfs / 'etc'
        etc.mkdir()
        (etc / 'passwd').write_text('root:x:0:0:root:/root:/bin/bash\n'
                                    'developer:x:1000:1000::/home/developer:/bin/bash\n')
        args = self.r.argv(['/bin/bash', '-l'], user='developer')
        self.assertIn('-i', args)
        self.assertEqual(args[args.index('-i') + 1], '1000:1000')
        self.assertNotIn('-0', args)
        self.assertIn(str(self.r.base / 'users/developer') + ':/home/developer', args)
        self.assertIn('HOME=/home/developer', args)

    def test_regular_user_name_is_validated_before_lookup(self):
        with self.assertRaisesRegex(ValueError, 'username'):
            self.r.account('developer;id')

    def test_regular_users_home_folder_maps_to_guest_home(self):
        etc = self.r.rootfs / 'etc'
        etc.mkdir()
        (etc / 'passwd').write_text('developer:x:1000:1000::/home/developer:/bin/bash\n')
        folder = self.r.base / 'users/developer/project'
        folder.mkdir(parents=True)
        args = self.r.argv(['/bin/bash'], str(folder), user='developer')
        self.assertEqual(args[args.index('-w') + 1], '/home/developer/project')

    def test_foreign_cwd_refused(self):
        with self.assertRaises(ValueError):
            self.r.argv(['bash'], '/etc')

    def test_shared_workspace_subfolder_kept(self):
        folder = self.r.workspace / 'hello world'
        folder.mkdir()
        args = self.r.argv(['bash'], str(folder))
        self.assertEqual(args[args.index('-w') + 1], str(folder))

    def test_guest_environment_has_no_android_injection(self):
        env = self.r.env()
        for name in ('LD_PRELOAD', 'NODE_OPTIONS', 'PYTHONHOME', 'BASH_ENV'):
            self.assertNotIn(name, env)
        self.assertEqual(env['PROOT_LOADER'], str(self.native.resolve() / 'libproot-loader.so'))

    def test_missing_native_loader_refused(self):
        (self.native / 'libproot-loader.so').unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing'):
            self.r.argv(['bash'])

    def test_lock_rejects_second_installer(self):
        with self.r.lock(), self.assertRaises(RuntimeError):
            with self.r.lock():
                pass

    def test_reinstall_cannot_replace_existing_rootfs(self):
        marker = self.r.rootfs / 'important'
        marker.write_text('keep')
        with self.assertRaises(RuntimeError):
            self.r.install()
        self.assertEqual(marker.read_text(), 'keep')

    def test_config_cannot_follow_symlink_parent(self):
        (self.r.rootfs / 'etc').symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.r.write_guest(self.r.rootfs, 'etc/evil', 'bad')
        self.assertFalse((self.base / 'evil').exists())

if __name__ == '__main__':
    unittest.main()
