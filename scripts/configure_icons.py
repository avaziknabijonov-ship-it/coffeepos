"""Apply the checked-in CoffeePOS icon to generated native projects."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
icon = root / 'assets/app-icon.png'
ios = root / 'ios/App/App/Assets.xcassets/AppIcon.appiconset'
if ios.is_dir():
    shutil.copyfile(icon, ios / 'AppIcon-512@2x.png')
android = root / 'android/app/src/main/res'
if android.is_dir():
    # Adaptive foreground is a vector; no raster renderer required in CI.
    for folder in android.glob('mipmap-*'):
        for old in folder.glob('ic_launcher*'):
            old.unlink()
    vector = '''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="128" android:viewportHeight="128">
<path android:fillColor="#1c1917" android:pathData="M0,0h128v128h-128z"/>
<path android:fillColor="#d97706" android:pathData="M35,46h52v29c0,15 -10,24 -26,24s-26,-9 -26,-24z"/>
<path android:strokeColor="#fafaf9" android:strokeWidth="7" android:strokeLineCap="round" android:fillColor="#00000000" android:pathData="M87,51h7a14,14 0,0 1,0 28h-8M47,32v-9M61,32v-9M75,32v-9M33,106h57"/>
</vector>'''
    # Vector launcher works on all supported Android versions (minSdk 23).
    for name in ('ic_launcher', 'ic_launcher_round', 'ic_launcher_foreground'):
        target = android / 'drawable' / (name + '.xml')
        target.parent.mkdir(exist_ok=True)
        target.write_text(vector)
    manifest = root / 'android/app/src/main/AndroidManifest.xml'
    text = manifest.read_text().replace('@mipmap/ic_launcher', '@drawable/ic_launcher')
    # Session/draft storage must not enter Android cloud/device-transfer backups.
    text = text.replace('android:allowBackup="true"', 'android:allowBackup="false"')
    manifest.write_text(text)
print('CoffeePOS native icons configured.')
