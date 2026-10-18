#!/usr/bin/env python3
"""Run the real runtime as the debug app UID. Does not install/replace any APK.
ADB run-as has a different SELinux domain; also validate from the UI terminal.
"""
import argparse, json, os, shlex, subprocess
from pathlib import Path
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--serial', required=True)
parser.add_argument('--package', default='com.vscodroid.linux.debug')
parser.add_argument('--archive', type=Path)
parser.add_argument('--action', choices=['diagnostics','toolchains','exec'], default='diagnostics')
parser.add_argument('command', nargs=argparse.REMAINDER, help='With --action exec: -- command arguments')
args = parser.parse_args()
adb = str(Path(os.environ.get('ANDROID_HOME', str(Path.home()/'Library/Android/sdk')))/'platform-tools/adb')
base = [adb,'-s',args.serial]
def command(*parts, data=None):
    return subprocess.run(base+list(parts),input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout.decode()
def shell(*parts):
    return command('shell',shlex.join(parts))
package_path = shell('pm','path',args.package).strip().removeprefix('package:')
native = str(Path(package_path).parent / 'lib/arm64')
files = shell('run-as',args.package,'pwd').strip() + '/files'
shell('run-as',args.package,'mkdir','-p',files+'/linux-test',files+'/linux/tmp',files+'/projects')
for name in ['runtime.py','rootfs.json']:
    command('shell','-T',shlex.join(['run-as',args.package,'sh','-c','cat > '+shlex.quote(files+'/linux-test/'+name)]),
            data=(root/'linux/extension'/name).read_bytes())
env = ['LD_LIBRARY_PATH='+native+':'+files+'/usr/lib','PYTHONHOME='+files+'/usr',
       'HOME='+files+'/home','TMPDIR='+files+'/linux/tmp','SSL_CERT_FILE='+files+'/usr/etc/tls/cert.pem']
launch=['run-as',args.package,'env',*env,'/system/bin/sh','-c','exec "$@"','--',native+'/libpython.so',files+'/linux-test/runtime.py',
        '--files',files,'--native',native,'--workspace',files+'/projects']
if args.archive:
    # Stream public, digest-verified bytes straight into this debug app's sandbox.
    with args.archive.open('rb') as stream:
        subprocess.run(base+['shell','-T',shlex.join(['run-as',args.package,'sh','-c',
            'cat > '+shlex.quote(files+'/linux-test/rootfs.tar.xz')])],stdin=stream,check=True)
    subprocess.run(base+['shell',shlex.join(launch+['install','--archive',files+'/linux-test/rootfs.tar.xz'])],check=True)
extra = args.command if args.action == 'exec' else []
if extra and extra[0] != '--':
    extra.insert(0, '--')
subprocess.run(base+['shell',shlex.join(launch+[args.action]+extra)],check=True)
print('App UID smoke finished; validate again inside the normal app process.')
