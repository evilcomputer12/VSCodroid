#!/usr/bin/env python3
"""Verified Code OSS updates; the APK's server and native runtime stay intact."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import tarfile
import time
import urllib.request

REPO = 'rmyndharis/VSCodroid'
API = f'https://api.github.com/repos/{REPO}/releases?per_page=100'
MAX_DOWNLOAD = 300 * 1024 * 1024
MAX_EXPANDED = 1200 * 1024 * 1024
INTERVAL = 24 * 3600
ADDONS = {
    'node-pty': 'build/Release/pty.node',
    '@parcel/watcher': 'build/Release/watcher.node',
    '@vscode/sqlite3': 'build/Release/vscode-sqlite3.node',
    '@vscode/spdlog': 'index.js',
}


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {} if default is None else default


def atomic(path, value):
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def sha256(file):
    digest = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Only stable three-part IDE versions are accepted')
    return tuple(map(int, value.split('.')))


def release_candidate(releases, current):
    candidates = []
    for release in releases:
        tag = release.get('tag_name', '')
        # Upstream labels its stable-source server assets prerelease to keep
        # them separate from APK releases. Never accept a semver prerelease.
        if release.get('draft') or not re.fullmatch(r'server-\d+\.\d+\.\d+', tag):
            continue
        v = tag.removeprefix('server-')
        if version(v) <= version(current):
            continue
        name = f'vscode-reh-web-linux-arm64-{v}.tar.gz'
        for asset in release.get('assets', []):
            digest = asset.get('digest') or ''
            url = asset.get('browser_download_url')
            if (asset.get('name') == name and re.fullmatch(r'sha256:[0-9a-f]{64}', digest)
                    and url == f'https://github.com/{REPO}/releases/download/{tag}/{name}'
                    and 0 < asset.get('size', 0) <= MAX_DOWNLOAD):
                candidates.append({'version': v, 'sha256': digest[7:], 'url': url,
                                   'size': asset['size']})
    return max(candidates, key=lambda c: version(c['version']), default=None)


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('Refusing a non-HTTPS release redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, target=None, limit=4 * 1024 * 1024, json_response=True):
    request = urllib.request.Request(url, headers={'User-Agent': 'VSCodroid-Linux-IDE-Updater',
                                                  'Accept': 'application/vnd.github+json' if url == API else '*/*'})
    opener = urllib.request.build_opener(HTTPSOnly(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    deadline = time.monotonic() + 900
    with opener.open(request, timeout=30) as response:
        with target.open('wb') if target else contextlib.nullcontext() as out:
            chunks, total = [], 0
            while chunk := response.read(256 * 1024):
                total += len(chunk)
                if total > limit or time.monotonic() > deadline:
                    raise ValueError('Release download exceeded its size or time limit')
                if out:
                    out.write(chunk)
                else:
                    chunks.append(chunk)
            return total if out else json.loads(b''.join(chunks)) if json_response else b''.join(chunks)


def required_node_major(commit):
    # Upstream deliberately omits glibc Node from the archive. Read the target
    # from the immutable VS Code source commit recorded inside the verified tree.
    data = fetch(f'https://raw.githubusercontent.com/microsoft/vscode/{commit}/remote/.npmrc',
                 limit=65536, json_response=False).decode('utf-8')
    match = re.search(r'^target="?(\d+)\.\d+\.\d+"?\s*$', data, re.M)
    if not match:
        raise ValueError('Could not identify the release Node ABI')
    return int(match.group(1))


def extract(archive, destination):
    """No links, devices, overwrites or paths outside a new private directory."""
    seen, total, count = set(), 0, 0
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            name = PurePosixPath(member.name)
            if name == PurePosixPath('.') and member.isdir():
                continue
            count += 1
            if (name.is_absolute() or '..' in name.parts or not name.parts or
                    '\\' in member.name or count > 60000 or
                    not (member.isdir() or member.isfile())):
                raise ValueError('Unsafe IDE archive entry: ' + member.name[:150])
            target = destination.joinpath(*name.parts)
            if name in seen:
                raise ValueError('Duplicate IDE archive entry')
            seen.add(name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            total += member.size
            if total > MAX_EXPANDED or member.size > 150 * 1024 * 1024:
                raise ValueError('IDE archive exceeds unpacked size limit')
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, target.open('xb') as out:
                shutil.copyfileobj(source, out, 256 * 1024)
            target.chmod(0o600)  # native executables still come from the APK


def adapt(tree, bundled, expected_version):
    product = read(tree / 'product.json')
    if (product.get('version') != expected_version or
            not re.fullmatch(r'[a-f0-9]{40}', product.get('commit', '')) or
            read(tree / 'package.json').get('version') != expected_version):
        raise ValueError('Release identity does not match its metadata')
    required = read(bundled / 'vscodroid-patches.json')
    delivered = read(tree / 'vscodroid-patches.json')
    if not required or any(delivered.get(k) != v for k, v in required.items()):
        raise ValueError('This release needs a newer Android app: Android patches changed')
    for entry in ['out/server-main.js', 'out/vs/code/browser/workbench/workbench.html',
                  'out/vs/workbench/api/node/extensionHostProcess.js', 'LICENSE.txt', 'ThirdPartyNotices.txt']:
        if not (tree / entry).is_file():
            raise ValueError('Incomplete IDE release: ' + entry)
    # Native libraries cannot be downloaded into nativeLibraryDir. Keep the
    # tested APK implementations, and only pair them with identical JS APIs.
    for package, replacement in ADDONS.items():
        old, new = (root / 'node_modules' / package for root in (bundled, tree))
        old_version = read(old / 'package.json').get('version')
        if not old_version or read(new / 'package.json').get('version') != old_version:
            raise ValueError('This release needs a newer Android app: ' + package + ' changed')
        (new / replacement).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old / replacement, new / replacement)
    # Other native payloads are only carried forward if byte-identical to the
    # APK's existing payload. Their Android shims are owned by the app too.
    allowed = {tree / 'node_modules' / p / f for p, f in ADDONS.items()}
    for file in tree.rglob('*.node'):
        if file not in allowed:
            if file == tree / 'node_modules/@vscode/spdlog/build/Release/spdlog.node':
                file.unlink()
                continue
            old = bundled / file.relative_to(tree)
            if not old.is_file() or sha256(old) != sha256(file):
                raise ValueError('This release needs a newer Android app: native payload changed: ' + str(file.relative_to(tree)))
    expected = read(bundled.parent / 'ide-compat.json').get('nodeMajor')
    if not expected or required_node_major(product['commit']) != expected:
        raise ValueError('This release needs a newer Android app: Node runtime changed')
    if (tree / 'node').exists():
        (tree / 'node').unlink()
    return product


class Updater:
    def __init__(self, files):
        self.server = Path(files) / 'server'
        self.bundled = self.server / 'vscode-reh'
        self.root = self.server / 'ide-updates'
        self.root.mkdir(parents=True, exist_ok=True)
        self.state = self.root / 'state.json'
        self.status = self.root / 'status.json'

    def record(self, message, **fields):
        data = {'checkedAt': int(time.time()), 'message': message, **fields}
        atomic(self.status, data)
        print(json.dumps(data), flush=True)
        return data

    def stage(self, archive, candidate):
        digest = sha256(archive)
        if digest != candidate['sha256']:
            raise ValueError('IDE download SHA-256 mismatch')
        versions = self.root / 'versions'
        versions.mkdir(exist_ok=True)
        destination = versions / digest
        staging = self.root / 'staging'
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        try:
            tree = staging / 'vscode-reh'
            tree.mkdir()
            extract(archive, tree)
            product = adapt(tree, self.bundled, candidate['version'])
            atomic(staging / 'verified.json', {**candidate, 'commit': product['commit']})
            if destination.exists():
                shutil.rmtree(staging)
            else:
                staging.rename(destination)
            state = read(self.state)
            state.update(pending=digest, baseCommit=read(self.bundled / 'product.json')['commit'],
                         baseApp=read(self.server / 'ide-compat.json').get('buildId'))
            atomic(self.state, state)
            return self.record(f"IDE {candidate['version']} downloaded. It will activate on the next full IDE start.",
                               version=candidate['version'], pending=digest)
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def check(self, force=False):
        previous = read(self.status)
        if not force and time.time() - previous.get('checkedAt', 0) < INTERVAL:
            print(json.dumps(previous))
            return previous
        state = read(self.state)
        if state.get('pending'):
            return self.record('An IDE update is ready for the next full IDE start.', pending=state['pending'])
        running = read(self.server / 'ide-running.json')
        current = running.get('version') or read(self.bundled / 'product.json')['version']
        candidate = release_candidate(fetch(API), current)
        if not candidate:
            return self.record(f'IDE {current} is the newest compatible release published by VSCodroid.', version=current)
        if candidate['sha256'] in state.get('blocked', []):
            return self.record('This release was rolled back. Waiting for a newer release.', version=candidate['version'])
        if shutil.disk_usage(self.root).free < MAX_EXPANDED + MAX_DOWNLOAD + 128 * 1024 * 1024:
            raise ValueError('Free at least 1.6 GiB to download and stage an IDE update')
        # Only our inactive version directories are eligible for cache cleanup.
        keep = {state.get(k) for k in ('active', 'previous', 'pending', 'trial')} | {running.get('id')}
        for item in (self.root / 'versions').glob('*') if (self.root / 'versions').exists() else []:
            if re.fullmatch('[a-f0-9]{64}', item.name) and item.name not in keep:
                shutil.rmtree(item)
        archive = self.root / 'download.tar.gz'
        try:
            size = fetch(candidate['url'], archive, MAX_DOWNLOAD)
            if size != candidate['size']:
                raise ValueError('IDE download length mismatch')
            return self.stage(archive, candidate)
        finally:
            archive.unlink(missing_ok=True)

    def rollback(self):
        state = read(self.state)
        active = state.get('active')
        state.update(pending='bundled', blocked=list(set(state.get('blocked', []) + ([active] if active else []))))
        atomic(self.state, state)
        return self.record('Bundled IDE selected for the next full IDE start. Projects and Linux home are preserved.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--files', required=True)
    parser.add_argument('action', choices=['check', 'rollback'])
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    updater = Updater(args.files)
    with (updater.root / 'download.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'message': 'An IDE update check is already running.'}))
            return
        try:
            updater.check(args.force) if args.action == 'check' else updater.rollback()
        except Exception as error:
            updater.record(str(error), error=True)
            raise SystemExit(1)


if __name__ == '__main__':
    main()
