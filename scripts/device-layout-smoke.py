#!/usr/bin/env python3
"""Capture both tablet orientations, restoring the user's rotation settings."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--serial', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
adb = str(Path(os.environ.get('ANDROID_HOME', str(Path.home() / 'Library/Android/sdk'))) / 'platform-tools/adb')
base = [adb, '-s', args.serial]


def shell(*parts):
    return subprocess.check_output(base + ['shell', *parts], text=True).strip()


settings = {key:shell('settings','get','system',key) for key in ('accelerometer_rotation','user_rotation')}
try:
    shell('settings','put','system','accelerometer_rotation','0')
    for label, rotation in [('portrait','0'), ('landscape','1')]:
        shell('settings','put','system','user_rotation',rotation)
        time.sleep(3)
        resumed = [line for line in shell('dumpsys','activity','activities').splitlines() if any(marker in line for marker in ('mResumedActivity', 'topResumedActivity', 'ResumedActivity:'))]
        if not any('com.vscodroid.linux.debug/' in line for line in resumed):
            raise RuntimeError('The debug fork is not in front; refusing to capture another app')
        png = subprocess.check_output(base + ['exec-out','screencap','-p'])
        target = root / 'output' / ('tablet-' + label + '.png')
        target.write_bytes(png)
        print(label, struct.unpack('>II', png[16:24]), target)
finally:
    for key, value in settings.items():
        if value == 'null':
            shell('settings','delete','system',key)
        else:
            shell('settings','put','system',key,value)
