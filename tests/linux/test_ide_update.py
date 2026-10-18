import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('ide_update', Path(__file__).resolve().parents[2] / 'linux/extension/ide_update.py')
u = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(u)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        node = patch.object(u, 'required_node_major', return_value=24)
        self.node = node.start()
        self.addCleanup(node.stop)

    def archive(self, entries):
        archive = self.root / 'release.tgz'
        with tarfile.open(archive, 'w:gz') as tar:
            for name, value in entries:
                member = tarfile.TarInfo(name)
                if isinstance(value, tuple):
                    member.type, member.linkname = value
                    tar.addfile(member)
                else:
                    member.size = len(value)
                    tar.addfile(member, io.BytesIO(value))
        return archive

    def candidate(self, v='1.140.0', **overrides):
        tag = 'server-' + v
        name = f'vscode-reh-web-linux-arm64-{v}.tar.gz'
        asset = {'name':name, 'digest':'sha256:' + 'a'*64, 'size':100,
                 'browser_download_url':f'https://github.com/{u.REPO}/releases/download/{tag}/{name}'}
        asset.update(overrides)
        return {'tag_name':tag,'prerelease':True,'assets':[asset]}

    def test_stable_server_channel_numeric_order(self):
        got = u.release_candidate([self.candidate('1.9.0'), self.candidate('1.140.0'),
                                   self.candidate('1.139.2')], '1.139.1')
        self.assertEqual(got['version'], '1.140.0')
        self.assertIsNone(u.release_candidate([self.candidate('1.139.1')], '1.139.1'))

    def test_untrusted_or_incomplete_metadata_rejected(self):
        for overrides in ({'digest':None}, {'digest':'sha256:no'}, {'size':u.MAX_DOWNLOAD+1},
                          {'browser_download_url':'https://example.com/payload'}, {'name':'x86.tar.gz'}):
            self.assertIsNone(u.release_candidate([self.candidate(**overrides)], '1.139.1'))
        for v in ('1.140.0-insiders','1.140.0-rc1'):
            self.assertIsNone(u.release_candidate([self.candidate(v)], '1.139.1'))

    def test_archive_rejects_traversal_links_devices_duplicates(self):
        for entries in ([('../escape',b'x')], [('/absolute',b'x')],
                        [('link',(tarfile.SYMTYPE,'/tmp'))], [('hard',(tarfile.LNKTYPE,'a'))],
                        [('device',(tarfile.CHRTYPE,''))], [('same',b'a'),('same',b'b')]):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory(dir=self.root) as directory:
                with self.assertRaises(ValueError):
                    u.extract(self.archive(entries), Path(directory))
        self.assertFalse((self.root.parent / 'escape').exists())

    def test_archive_limit(self):
        with patch.object(u, 'MAX_EXPANDED', 2), self.assertRaises(ValueError):
            u.extract(self.archive([('large',b'abc')]), self.root / 'extract')

    def test_digest_failure_leaves_active_tree_untouched(self):
        updater = u.Updater(self.root)
        u.atomic(updater.state, {'active':'b'*64})
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            updater.stage(self.archive([('file',b'x')]), {'sha256':'a'*64, 'version':'1.140.0'})
        self.assertEqual(u.read(updater.state), {'active':'b'*64})

    def fixture(self):
        bundled = self.root / 'server/vscode-reh'
        tree = self.root / 'new'
        for root in (bundled, tree):
            root.mkdir(parents=True)
            u.atomic(root / 'product.json', {'version':'1.140.0','commit':'c'*40})
            u.atomic(root / 'package.json', {'version':'1.140.0'})
            u.atomic(root / 'vscodroid-patches.json', {'required.patch':'hash'})
            for package, replacement in u.ADDONS.items():
                p = root / 'node_modules' / package
                (p / replacement).parent.mkdir(parents=True)
                u.atomic(p / 'package.json', {'version':'1.0'})
                (p / replacement).write_text('android' if root == bundled else 'glibc')
        u.atomic(bundled.parent / 'ide-compat.json', {'nodeMajor':24})
        for name in ['out/server-main.js','out/vs/code/browser/workbench/workbench.html',
                     'out/vs/workbench/api/node/extensionHostProcess.js','LICENSE.txt','ThirdPartyNotices.txt']:
            p = tree / name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('code')
        (tree / 'node').write_bytes(b'ELF\0v24.18.0\0')
        return bundled, tree

    def test_adaptation_uses_apk_native_addons(self):
        bundled, tree = self.fixture()
        u.adapt(tree,bundled,'1.140.0')
        self.assertFalse((tree / 'node').exists())
        self.assertFalse((tree / 'unknown.node').exists())
        self.assertEqual((tree / 'node_modules/node-pty/build/Release/pty.node').read_text(),'android')

    def test_patch_change_requires_app_update(self):
        bundled, tree = self.fixture()
        u.atomic(tree / 'vscodroid-patches.json', {'required.patch':'new'})
        with self.assertRaisesRegex(ValueError, 'patches changed'): u.adapt(tree,bundled,'1.140.0')

    def test_native_api_change_requires_app_update(self):
        bundled, tree = self.fixture()
        u.atomic(tree / 'node_modules/node-pty/package.json', {'version':'2'})
        with self.assertRaisesRegex(ValueError, 'node-pty changed'): u.adapt(tree,bundled,'1.140.0')

    def test_node_abi_change_requires_app_update(self):
        bundled, tree = self.fixture()
        self.node.return_value = 26
        with self.assertRaisesRegex(ValueError, 'Node runtime changed'): u.adapt(tree,bundled,'1.140.0')

    def test_unknown_native_payload_requires_app_update(self):
        bundled, tree = self.fixture()
        (tree / 'unknown.node').write_bytes(b'glibc')
        with self.assertRaisesRegex(ValueError, 'native payload changed'): u.adapt(tree,bundled,'1.140.0')

    def test_daily_throttle_avoids_network(self):
        updater = u.Updater(self.root)
        u.atomic(updater.status, {'checkedAt':u.time.time(),'message':'current'})
        with patch.object(u,'fetch') as fetch:
            updater.check()
            fetch.assert_not_called()

    def test_manual_rollback_queues_without_replacing_live_tree(self):
        updater = u.Updater(self.root)
        u.atomic(updater.state, {'active':'b'*64})
        updater.rollback()
        self.assertEqual(u.read(updater.state)['active'],'b'*64)
        self.assertEqual(u.read(updater.state)['pending'],'bundled')


if __name__ == '__main__': unittest.main()
