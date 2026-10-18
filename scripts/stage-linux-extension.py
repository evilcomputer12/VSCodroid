#!/usr/bin/env python3
"""Copy owned Linux extensions into the asset tree, without build caches."""
from pathlib import Path
import json
import re
import shutil
root = Path(__file__).resolve().parents[1]
assets = root / 'android/app/src/main/assets/extensions'
node_pin = root / 'android/app/src/main/jniLibs/arm64-v8a/.libnode-version'
if node_pin.exists():
    major = int(re.search(r'\d+', node_pin.read_text()).group())
    build_id = re.search(r'versionCode = (\d+)', (root / 'android/app/build.gradle.kts').read_text()).group(1)
    (assets.parent / 'ide-compat.json').write_text(json.dumps({'nodeMajor': major, 'buildId': build_id}) + '\n')
for source in ('extension', 'ui'):
    metadata = json.loads((root / 'linux' / source / 'package.json').read_text())
    prefix = metadata['publisher'] + '.' + metadata['name'] + '-'
    name = prefix + metadata['version']
    for old in assets.glob(prefix + '*'):
        if old.is_dir() and old.name != name and re.fullmatch(r'\d+\.\d+\.\d+', old.name[len(prefix):]):
            shutil.rmtree(old)
    target = assets / name
    target.mkdir(parents=True, exist_ok=True)
    for file in (root / 'linux' / source).iterdir():
        if file.is_file() and file.suffix in ('.js', '.json', '.py'):
            shutil.copy2(file, target / file.name)
    print('Staged', name)
