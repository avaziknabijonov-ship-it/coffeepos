"""Repeatable Google Play SDK settings for generated Capacitor 7 projects."""
import os
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'android'
if not root.is_dir():
    raise SystemExit('Run npx cap add android first.')

def replace(path, pattern, value):
    text, count = re.subn(pattern, value, path.read_text())
    if count != 1:
        raise SystemExit(f'Unexpected Android scaffold: {path.name} ({count} matches)')
    path.write_text(text)

replace(root/'variables.gradle', r'compileSdkVersion = \d+', 'compileSdkVersion = 36')
replace(root/'variables.gradle', r'targetSdkVersion = \d+', 'targetSdkVersion = 36')
replace(root/'build.gradle', r'com.android.tools.build:gradle:[^\s\x27]+', 'com.android.tools.build:gradle:8.10.1')
replace(root/'gradle/wrapper/gradle-wrapper.properties', r'gradle-[\d.]+-all.zip', 'gradle-8.11.1-all.zip')
code = os.environ.get('COFFEEPOS_BUILD_NUMBER', '1')
if not code.isdigit() or not 0 < int(code) < 2100000000:
    raise SystemExit('COFFEEPOS_BUILD_NUMBER must be a positive integer < 2100000000')
replace(root/'app/build.gradle', r'versionCode \d+', f'versionCode {code}')
replace(root/'app/build.gradle', r'versionName "[^"]+"', 'versionName "1.0.0"')
print('Android configured: target/compile SDK 36, AGP 8.10.1, release version 1.0.0.')
