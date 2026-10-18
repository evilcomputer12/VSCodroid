#!/usr/bin/env python3
"""Copy owned Linux extensions into the asset tree, without build caches."""
from pathlib import Path
import shutil
root = Path(__file__).resolve().parents[1]
assets = root / 'android/app/src/main/assets/extensions'
for source, name in [('extension','vscodroid.vscodroid-linux-0.1.0'), ('ui','vscodroid.vscodroid-linux-ui-0.1.0')]:
    target = assets / name
    target.mkdir(parents=True, exist_ok=True)
    for file in (root / 'linux' / source).iterdir():
        if file.is_file() and file.suffix in ('.js', '.json', '.py'):
            shutil.copy2(file, target / file.name)
    print('Staged', name)
