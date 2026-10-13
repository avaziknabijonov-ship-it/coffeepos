# CoffeePOS Hybrid — Android APK (TEST COFFEE)

This procedure builds a **new APK** from this branch; an older installed APK will not get the new server settings automatically. Back up the existing app/data before replacing anything. Do not modify the live MasterCoffee database.

## Windows: run the TEST backend

Open a CMD terminal in the project root (the folder containing `package.json`).

```cmd
set "PYTHONPATH=%CD%\backend"
py -3.12 -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Keep this terminal open. Ensure `http://127.0.0.1:8000/healthz` returns `{"ok":true}` **in a computer browser**. This is the actual health endpoint; `/docs` may not be available on all installations.

The computer and phone must be on the same Wi-Fi. To find the computer's current IP:

```cmd
ipconfig
```

In phone Chrome, check `http://<CURRENT-LAN-IP>:8000/healthz`. A firewall rule for TCP port 8000 may be needed on a **Private** network; do not disable the firewall.

## Build Android app

Requirements: Node.js, Android Studio and Android SDK. From the project root:

```cmd
npm install
npx cap add android
npm run android:sync
npm run android:open
```

Run `npx cap add android` only the first time, when the `android` directory doesn't exist. If it already exists, skip that command. In Android Studio, build and install a debug APK.

The source file `capacitor.config.ts` is in the repository root. Android native project files may be generated locally and are not necessarily included in the repository.

## Login setup on new APK

1. Open the new CoffeePOS Hybrid APK.
2. At the bottom of the login screen, open **Server sozlamalari**.
3. Enter `http://<CURRENT-LAN-IP>:8000` (e.g. `http://192.168.1.26:8000` only while that is the actual IP).
4. Tap **Serverni tekshirish va saqlash**. It verifies `/healthz`.
5. Only then enter the TEST COFFEE company login and PIN (do not post PINs or tokens in chat).

If Wi-Fi reassigns the computer's IP, edit the server setting again. Changing the server clears the old session token.

**Security:** Plain HTTP is supported only for isolated private-LAN testing; production servers must use HTTPS. Android LAN cleartext support is enabled in `capacitor.config.ts` for this development build and should be reviewed for production distribution. All server routes should be protected and role permissions verified on the backend, not only hidden in the UI.

## Problems to troubleshoot

- No health response in phone Chrome: wrong computer IP, Wi-Fi client isolation, backend not listening on `0.0.0.0`, or Windows Firewall.
- `{"detail":"Not Found"}` at `/` is not a connectivity failure; check `/healthz`.
- Health works in Chrome but APK doesn't connect: rebuild from the latest source, ensure the server address was **saved**, and inspect Android WebView/network policy errors.
- Wrong login/PIN after health succeeds: verify the company slug and PIN against **the same backend database**; the TEST COFFEE database may differ from other test or production backends.
- The Python test suite must import `backend/app` from **this checkout**, not `C:\CoffeePoss\yangi-versiya`.
