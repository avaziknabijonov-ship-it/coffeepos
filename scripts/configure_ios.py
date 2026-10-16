"""Apply repeatable iOS settings after cap add/sync (no signing credentials)."""
import plistlib
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'ios/App/App/Info.plist'
if not path.is_file():
    raise SystemExit('Run npx cap add ios first (on a Mac for native builds).')
with path.open('rb') as source:
    settings = plistlib.load(source)
settings['NSLocalNetworkUsageDescription'] = 'CoffeePOS connects to your cafe server on the local Wi-Fi network to manage sales and inventory.'
settings.setdefault('NSAppTransportSecurity', {})['NSAllowsLocalNetworking'] = True
with path.open('wb') as destination:
    plistlib.dump(settings, destination, sort_keys=False)
print('iOS local-network description configured. Use HTTPS for hosted APIs.')
