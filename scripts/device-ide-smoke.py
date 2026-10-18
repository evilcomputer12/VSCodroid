#!/usr/bin/env python3
"""Exercise the updater's full staging path with the current real release.

Only for the task-owned debug package. It does not pretend a newer release exists.
Restart the app afterward to verify promotion; then use Restore Bundled IDE.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--serial', required=True)
args = parser.parse_args()
package = 'com.vscodroid.linux.debug'
adb = str(Path(os.environ.get('ANDROID_HOME', str(Path.home() / 'Library/Android/sdk'))) / 'platform-tools/adb')
base = [adb, '-s', args.serial]


def shell(parts):
    return subprocess.check_output(base + ['shell', shlex.join(parts)], text=True).strip()


native = str(Path(shell(['pm', 'path', package]).removeprefix('package:')).parent / 'lib/arm64')
files = shell(['run-as', package, 'pwd']) + '/files'
script = '''import sys
from pathlib import Path
files = Path(sys.argv[1])
extensions = files / 'home/.vscodroid/extensions'
installed = sorted(extensions.glob('vscodroid.vscodroid-linux-*'), key=lambda p: tuple(map(int,p.name.rsplit('-',1)[1].split('.'))))
sys.path.insert(0, str(installed[-1]))
import ide_update as u
updater = u.Updater(files)
candidate = u.release_candidate(u.fetch(u.API), '0.0.0')
assert candidate['version'] == u.read(updater.bundled / 'product.json')['version'], 'Test requires current release'
archive = updater.root / 'current-release-test.tar.gz'
try:
    print('Downloading the actual current release to test staging, not claiming a newer IDE.', flush=True)
    assert u.fetch(candidate['url'], archive, u.MAX_DOWNLOAD) == candidate['size']
    updater.stage(archive, candidate)
finally:
    archive.unlink(missing_ok=True)
'''
shell(['run-as', package, 'mkdir', '-p', files + '/ide-test'])
target = files + '/ide-test/stage-current.py'
subprocess.run(base + ['shell', '-T', shlex.join(['run-as', package, 'sh', '-c', 'cat > ' + shlex.quote(target)])],
               input=script.encode(), check=True)
env = ['LD_LIBRARY_PATH=' + native + ':' + files + '/usr/lib', 'PYTHONHOME=' + files + '/usr',
       'HOME=' + files + '/home', 'SSL_CERT_FILE=' + files + '/usr/etc/tls/cert.pem']
subprocess.run(base + ['shell', shlex.join(['run-as', package, 'env', *env, '/system/bin/sh',
    '-c', 'exec "$@"', '--', native + '/libpython.so', target, files])], check=True)
