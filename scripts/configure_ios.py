"""Apply repeatable iOS settings after cap add/sync (no signing credentials)."""
import os
import re
import plistlib
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'ios/App/App/Info.plist'
if not path.is_file():
    raise SystemExit('Run npx cap add ios first (on a Mac for native builds).')
with path.open('rb') as source:
    settings = plistlib.load(source)
settings['CFBundleDisplayName'] = 'CoffeePOS TEST' if os.environ.get('COFFEEPOS_TEST_APP') == '1' else 'CoffeePOS'
settings['NSLocalNetworkUsageDescription'] = 'CoffeePOS connects to your cafe server on the local Wi-Fi network to manage sales and inventory.'
settings.setdefault('NSAppTransportSecurity', {})['NSAllowsLocalNetworking'] = True
with path.open('wb') as destination:
    plistlib.dump(settings, destination, sort_keys=False)
project = path.parents[1] / 'App.xcodeproj/project.pbxproj'
code = os.environ.get('COFFEEPOS_BUILD_NUMBER', '1')
if not code.isdigit() or int(code) < 1:
    raise SystemExit('Invalid COFFEEPOS_BUILD_NUMBER')
text = project.read_text()
text = re.sub(r'CURRENT_PROJECT_VERSION = [^;]+;', f'CURRENT_PROJECT_VERSION = {code};', text)
text = re.sub(r'MARKETING_VERSION = [^;]+;', 'MARKETING_VERSION = 1.0.0;', text)
project.write_text(text)
print('iOS local-network description configured. Use HTTPS for hosted APIs.')
