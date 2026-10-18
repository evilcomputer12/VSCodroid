#!/usr/bin/env python3
"""Verified Debian installer and argv-based PRoot launcher. No privileged operations."""
import argparse
import contextlib
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

MANIFEST = json.loads(Path(__file__).with_name('rootfs.json').read_text())
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_EXTRACTED = 2 * 1024 * 1024 * 1024
MAX_MEMBERS = 150000
PACKAGES = ['build-essential', 'clang', 'clangd', 'gdb', 'cmake', 'make', 'git',
            'openssh-client', 'ca-certificates', 'python3', 'python3-pip', 'python3-venv',
            'nodejs', 'npm', 'default-jdk-headless', 'maven', 'gradle', 'pkg-config',
            'docker-cli', 'docker-compose', 'docker-buildx']


def emit(phase, message, **data):
    print(json.dumps(dict(phase=phase, message=message, **data)), flush=True)


def atomic_json(file, data):
    tmp = file.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    os.chmod(tmp, 0o600)
    os.replace(tmp, file)


def archive_path(name, strip=1):
    """Reject ambiguous paths before stripping; never use tarfile.extract(all)."""
    if '\x00' in name or '\\' in name or name.startswith('/'):
        raise ValueError('Unsafe archive path: ' + repr(name))
    parts = [p for p in name.split('/') if p not in ('', '.')]
    if '..' in parts:
        raise ValueError('Archive traversal: ' + repr(name))
    return Path(*parts[strip:]) if len(parts) > strip else None


def safe_extract(archive, destination, strip=1):
    """Extract only dirs/files/links. Defer ALL links so writes cannot follow them.

    Absolute symlinks are guest paths; they are never followed during extraction.
    Device nodes under /dev are omitted because Android's /dev is bound at launch.
    Hard links must target a regular, extracted file, never a link or host path.
    """
    destination = Path(destination)
    if not destination.is_dir() or any(destination.iterdir()):
        raise ValueError('Extraction requires a fresh empty directory')
    links, seen, regular, size = [], set(), set(), 0
    with tarfile.open(archive, 'r:*') as tar:
        for count, member in enumerate(tar, 1):
            if count > MAX_MEMBERS:
                raise ValueError('Too many archive members')
            rel = archive_path(member.name, strip)
            if rel is None:
                continue
            target = destination / rel
            if member.isdir():
                if rel in seen and not target.is_dir():
                    raise ValueError('Conflicting archive directory')
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, (member.mode & 0o777) | 0o700)
                continue
            if rel in seen:
                raise ValueError('Duplicate archive entry: ' + str(rel))
            seen.add(rel)
            if member.ischr() or member.isblk() or member.isfifo():
                if rel.parts[0] != 'dev':
                    raise ValueError('Special file outside dev')
                continue
            if not (member.isfile() or member.issym() or member.islnk()):
                raise ValueError('Unsupported archive member')
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.issym() or member.islnk():
                if not member.linkname or '\x00' in member.linkname:
                    raise ValueError('Invalid link target')
                links.append((rel, member))
                continue
            size += member.size
            if member.size < 0 or size > MAX_EXTRACTED:
                raise ValueError('Extracted size exceeds limit')
            with tar.extractfile(member) as src, target.open('xb') as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
            os.chmod(target, (member.mode & 0o777) | 0o600)
            regular.add(rel)
            if count % 1000 == 0:
                emit('extracting', 'Extracting Debian', files=count, bytes=size)
    # Hardlinks first. Every parent must still be a directory, not a deferred link.
    for rel, member in links:
        if member.islnk():
            source = archive_path(member.linkname, strip)
            if source not in regular:
                raise ValueError('Hard link does not target an extracted regular file')
            os.link(destination / source, destination / rel)
    for rel, member in links:
        if member.issym():
            # A path with children cannot also become a symlink; os.symlink fails.
            os.symlink(member.linkname, destination / rel)
    return size


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('Refusing non-HTTPS redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_archive(file):
    digest = hashlib.sha256()
    with open(file, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != MANIFEST['sha256']:
        raise ValueError('Debian SHA-256 mismatch; no files were installed')


def download(file):
    if file.exists():
        verify_archive(file)
        return
    part = file.with_suffix('.part')
    opener = urllib.request.build_opener(HTTPSOnly())
    size, reported = 0, 0
    try:
        with opener.open(MANIFEST['url'], timeout=30) as src, part.open('wb') as out:
            total = int(src.headers.get('Content-Length', 0))
            if total > MAX_ARCHIVE:
                raise ValueError('Archive exceeds download limit')
            while True:
                block = src.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > MAX_ARCHIVE:
                    raise ValueError('Archive exceeds download limit')
                out.write(block)
                if time.monotonic() - reported > 0.5:
                    emit('downloading', 'Downloading verified Debian image', bytes=size, total=total)
                    reported = time.monotonic()
        verify_archive(part)
        os.replace(part, file)
    finally:
        part.unlink(missing_ok=True)


class Runtime:
    def __init__(self, files, native, workspace):
        self.files = Path(files).resolve()
        self.native = Path(native).resolve()
        self.workspace = Path(workspace).resolve()
        self.base = self.files / 'linux'
        self.rootfs = self.base / 'rootfs'
        self.home = self.base / 'home'
        self.tmp = self.base / 'tmp'
        for p in (self.base, self.home, self.tmp, self.workspace):
            p.mkdir(parents=True, exist_ok=True)
        self.state = self.base / 'state.json'

    @contextlib.contextmanager
    def lock(self):
        with (self.base / 'install.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Another Linux setup is already running')
            yield

    def write_guest(self, root, name, text, mode=0o644):
        # Configuration writes are confined to non-symlink parents in staging.
        target = root / name
        parent = target.parent
        while parent != root:
            if parent.is_symlink():
                raise ValueError('Symlink in configuration path')
            parent = parent.parent
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            target.unlink()
        target.write_text(text)
        os.chmod(target, mode)

    def install(self, archive=None, dns=('1.1.1.1', '8.8.8.8')):
        with self.lock():
            if self.rootfs.exists():
                if not self.state.is_file():
                    marker = self.rootfs / '.vscodroid-install.json'
                    if not marker.is_file() or marker.is_symlink():
                        raise RuntimeError('Existing rootfs has no install record; refusing to replace it')
                    record = json.loads(marker.read_text())
                    if record.get('sha256') != MANIFEST['sha256']:
                        raise RuntimeError('Existing rootfs install record does not match this image')
                    atomic_json(self.state, record)
                emit('installed', 'Debian is already installed')
                return
            # Only abandoned staging trees owned by this installer, never user home.
            for stage in self.base.glob('install-*'):
                if stage.is_dir() and not stage.is_symlink():
                    shutil.rmtree(stage)
            if shutil.disk_usage(self.base).free < 4 * 1024**3:
                raise RuntimeError('At least 4 GiB free is required for Debian and toolchains')
            for server in dns:
                ipaddress.ip_address(server)
            image = Path(archive) if archive else self.base / 'debian.tar.xz'
            if archive:
                verify_archive(image)
            else:
                download(image)
            staging = Path(tempfile.mkdtemp(prefix='install-', dir=self.base))
            try:
                emit('extracting', 'Verified SHA-256; extracting into staging')
                size = safe_extract(image, staging, MANIFEST['stripComponents'])
                if not (staging / 'usr/bin/bash').is_file():
                    raise ValueError('Rootfs has no bash executable')
                self.write_guest(staging, 'etc/resolv.conf', ''.join('nameserver ' + s + '\n' for s in dns))
                self.write_guest(staging, 'etc/hosts', '127.0.0.1 localhost\n::1 localhost\n')
                # Fake UID 0 is for dpkg, not a privilege escalation. No services.
                self.write_guest(staging, 'usr/sbin/policy-rc.d', '#!/bin/sh\nexit 101\n', 0o755)
                self.write_guest(staging, 'etc/apt/apt.conf.d/99vscodroid',
                                 'APT::Sandbox::User "root";\nAcquire::Retries "2";\n')
                self.write_guest(staging, 'etc/apt/sources.list', '')
                self.write_guest(staging, 'etc/apt/sources.list.d/debian.sources',
                                 'Types: deb\nURIs: https://deb.debian.org/debian\n'
                                 'Suites: trixie trixie-updates\nComponents: main\n'
                                 'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\n'
                                 'Types: deb\nURIs: https://security.debian.org/debian-security\n'
                                 'Suites: trixie-security\nComponents: main\n'
                                 'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n')
                for name in ('proc', 'sys', 'dev', 'tmp', 'root', 'workspace'):
                    (staging / name).mkdir(exist_ok=True)
                record = dict(schema=1, installed=True, toolchains=False,
                              sha256=MANIFEST['sha256'], extractedBytes=size)
                atomic_json(staging / '.vscodroid-install.json', record)
                os.replace(staging, self.rootfs)
                atomic_json(self.state, record)
                emit('installed', 'Debian installed. Run diagnostics, then install toolchains.')
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            if not archive:
                image.unlink(missing_ok=True)

    def argv(self, command, cwd=None, root=None):
        root = root or self.rootfs
        if not (root / 'usr/bin/bash').is_file():
            raise RuntimeError('Install Debian before opening a Linux terminal')
        proot = self.native / 'libproot.so'
        loader = self.native / 'libproot-loader.so'
        for binary in (proot, loader):
            if not binary.is_file():
                raise RuntimeError('APK is missing ' + binary.name + '; rebuild with download-proot.sh')
        workdir = str(self.workspace)
        if cwd:
            candidate = Path(cwd).resolve()
            if candidate == self.workspace or self.workspace in candidate.parents:
                workdir = str(candidate)
            elif candidate == self.home or self.home in candidate.parents:
                workdir = str(candidate)
            else:
                raise ValueError('Linux working directory must be inside the shared workspace or Linux home')
        args = [str(proot), '--kill-on-exit', '--link2symlink', '-0', '-r', str(root),
                '-b', '/dev', '-b', '/proc', '-b', '/sys',
                '-b', str(self.tmp) + ':/tmp', '-b', str(self.home) + ':/root',
                '-b', str(self.home) + ':' + str(self.home),
                '-b', str(self.workspace) + ':/workspace',
                '-b', str(self.workspace) + ':' + str(self.workspace), '-w', workdir,
                '/usr/bin/env', '-i', 'HOME=/root', 'USER=root', 'LOGNAME=root',
                'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                'TERM=xterm-256color', 'COLORTERM=truecolor', 'LANG=C.UTF-8',
                'TMPDIR=/tmp', 'SHELL=/bin/bash', 'VSCODROID_LINUX=1']
        return args + list(command)

    def env(self):
        # Never preload Bionic shims or host Node/Python options into glibc.
        return dict(PATH='/system/bin', HOME=str(self.home), TMPDIR=str(self.tmp),
                    LD_LIBRARY_PATH=str(self.native) + ':' + str(self.files / 'usr/lib'),
                    PROOT_LOADER=str(self.native / 'libproot-loader.so'),
                    PROOT_TMP_DIR=str(self.tmp), PROOT_NO_SECCOMP='1')

    def run(self, command, timeout=None):
        return subprocess.run(self.argv(command), env=self.env(), timeout=timeout, check=True)

    def toolchains(self):
        with self.lock():
            # Recover a cancelled package transaction before installing more packages.
            self.run(['/usr/bin/env', 'DEBIAN_FRONTEND=noninteractive',
                      'dpkg', '--configure', '-a'], timeout=600)
            self.run(['/usr/bin/apt-get', 'update'], timeout=600)
            self.run(['/usr/bin/env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get',
                      'install', '-y', '--no-install-recommends'] + PACKAGES, timeout=3600)
            record = json.loads(self.state.read_text())
            record['toolchains'] = True
            atomic_json(self.state, record)
            emit('ready', 'Development tools and Docker clients installed')

    def diagnostics(self):
        result = dict(installed=self.rootfs.is_dir(), freeBytes=shutil.disk_usage(self.base).free,
                      nativeProot=(self.native / 'libproot.so').is_file(),
                      nativeLoader=(self.native / 'libproot-loader.so').is_file(),
                      workspace=str(self.workspace), home=str(self.home), localDockerEngine=False)
        if self.state.is_file():
            result['installation'] = json.loads(self.state.read_text())
        if result['installed']:
            try:
                check = subprocess.run(self.argv(['/bin/bash', '-lc',
                    'printf "debian-ready\\n"; uname -m; for t in apt gcc clang cmake make git ssh python3 node npm java mvn gradle docker; do command -v "$t" || true; done; docker compose version 2>/dev/null || true']),
                    env=self.env(), capture_output=True, text=True, timeout=30)
                result.update(exitCode=check.returncode, output=check.stdout[-8192:], error=check.stderr[-8192:])
            except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
                result.update(exitCode=-1, error=str(error))
        print(json.dumps(result, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--files', default=os.environ.get('VSCODROID_FILES_DIR'), required=not os.environ.get('VSCODROID_FILES_DIR'))
    parser.add_argument('--native', default=os.environ.get('VSCODROID_NATIVE_DIR'), required=not os.environ.get('VSCODROID_NATIVE_DIR'))
    parser.add_argument('--workspace', default=os.environ.get('VSCODROID_WORKSPACE'), required=not os.environ.get('VSCODROID_WORKSPACE'))
    sub = parser.add_subparsers(dest='action', required=True)
    install = sub.add_parser('install')
    install.add_argument('--archive')
    install.add_argument('--dns', nargs='+', default=['1.1.1.1', '8.8.8.8'])
    sub.add_parser('diagnostics')
    sub.add_parser('toolchains')
    run = sub.add_parser('exec')
    run.add_argument('--cwd')
    run.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    runtime = Runtime(args.files, args.native, args.workspace)
    if args.action == 'install':
        runtime.install(args.archive, args.dns)
    elif args.action == 'toolchains':
        runtime.toolchains()
    elif args.action == 'diagnostics':
        runtime.diagnostics()
    elif args.action == 'exec':
        command = args.command
        if command and command[0] == '--':
            command = command[1:]
        os.execve(runtime.argv(command or ['/bin/bash', '-l'], args.cwd)[0],
                  runtime.argv(command or ['/bin/bash', '-l'], args.cwd), runtime.env())


if __name__ == '__main__':
    # SIGTERM from the setup UI unwinds extraction's finally block.
    def cancelled(_signal, _frame):
        raise KeyboardInterrupt('Linux operation cancelled')
    signal.signal(signal.SIGTERM, cancelled)
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        emit('error', str(error))
        sys.exit(1)
