# CoffeePOS for iPhone and iPad

Status: iOS integration and repeatable simulator build workflow. An installable,
signed IPA and TestFlight release require Apple signing credentials and an
Apple Developer account. A simulator .app cannot be installed on an iPhone.

The generated native project is not checked in. Its repeatable settings live
in capacitor.config.ts and scripts/configure_ios.py. Native project changes
must be added to that script so regeneration does not lose them.

## Mac setup

Use a Mac with Xcode and CocoaPods supported by Capacitor 7. Install project
dependencies with Node 22 or later:

```sh
npm ci
npm run build
# Optional separate test identity, set before generating the native scaffold:
export COFFEEPOS_TEST_APP=1
npx cap add ios
npm run ios:sync
npm run ios:open
```

For existing scaffold updates use ios:sync; do not repeat cap add ios.
The test identity is uz.coffeepos.hybrid.test; standard identity is
uz.coffeepos.hybrid. Do not mix identities when updating an installed build.

## Server and permissions

On the native login screen, open Server settings and enter the existing API
address. A hosted API must use HTTPS. The default iOS WebView origin is
capacitor://localhost; include it in the backend CORS_ORIGINS alongside the
existing web and Android origins. The Render blueprint includes this origin,
but an existing deployment requires its environment setting to be updated.

For cafe LAN testing, connect iPhone/iPad and the Windows server to the same
Wi-Fi. Use the computer's current LAN IP and port 8000, not localhost, on the
phone. Allow local-network access when iOS asks. Check /healthz in Safari first.
NSAllowsLocalNetworking is configured without disabling ATS globally; verify
HTTP access on the actual target iOS version and use HTTPS if ATS rejects it.

## Device release

In Xcode choose the App target and the correct Apple development team. Use
unique version/build numbers, archive for a generic iOS device, then distribute
with App Store Connect / TestFlight. The repository and CI deliberately contain
no signing certificates, passwords, or App Store Connect API keys.

Before device release, verify login, sales, warehouse creation, discounts,
shift closing, keyboard/safe areas, rotations and printing on both iPhone and
iPad. Floor layout and unpaid table carts currently remain device-local.
Bluetooth/USB printer compatibility on Android does not establish iOS printer
support; test the specific printer on iOS separately.
