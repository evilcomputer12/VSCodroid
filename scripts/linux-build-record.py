#!/usr/bin/env python3
import hashlib, json, subprocess, zipfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
def digest(file):
    h=hashlib.sha256()
    with file.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''): h.update(part)
    return h.hexdigest()
apk = root/'output/vscodroid-linux-debug.apk'
files = [apk]
extensions = {}
if apk.is_file():
    with zipfile.ZipFile(apk) as archive:
        for source in ('extension', 'ui'):
            directory = root/'linux'/source
            metadata = json.loads((directory/'package.json').read_text())
            name = metadata['publisher']+'.'+metadata['name']+'-'+metadata['version']
            extensions[name] = metadata['version']
            for file in directory.iterdir():
                if file.is_file() and file.suffix in ('.js','.json','.py'):
                    if archive.read('assets/extensions/'+name+'/'+file.name) != file.read_bytes():
                        raise SystemExit('APK contains a stale bundled extension: '+name+'/'+file.name)
        for name in ('server.js','ide-loader.js','ide-compat.json'):
            if archive.read('assets/'+name) != (root/'android/app/src/main/assets'/name).read_bytes():
                raise SystemExit('APK contains a stale server asset: '+name)
files += sorted((root/'android/app/src/main/jniLibs/arm64-v8a').glob('*.so'))
print(json.dumps({'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
    'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)),
    'ideVersion':(root/'VSCODE_VERSION').read_text().strip(),
    'extensions':extensions,
    'rootfs':json.loads((root/'linux/extension/rootfs.json').read_text()),
    'sha256':{str(f.relative_to(root)):digest(f) for f in files if f.is_file()}},indent=2))
