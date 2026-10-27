#!/usr/bin/env python3
"""Cross-module staging smoke test over HTTP (stdlib only). Refuses non-local targets.

Usage: python3 scripts/staging_smoke.py http://127.0.0.1:8080 [SUPERADMIN_KEY]
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080").rstrip("/")
if urllib.parse.urlparse(BASE).hostname not in ("127.0.0.1", "localhost"):
    sys.exit("Refusing to run against a non-local host (production safety).")
results: list[tuple[str, bool, str]] = []


def call(method, path, body=None, headers=None, raw=False):
    req = urllib.request.Request(BASE + path, method=method, headers={"Content-Type": "application/json", **(headers or {})},
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read().decode()
            return resp.status, data if raw else (json.loads(data) if data else None)
    except urllib.error.HTTPError as exc:
        data = exc.read().decode()
        try:
            return exc.code, json.loads(data)
        except ValueError:
            return exc.code, data


def check(name, ok, info=""):
    results.append((name, bool(ok), str(info)[:160]))


def key():
    return uuid.uuid4().hex


for _ in range(60):  # nginx can answer before the API finished startup (502)
    if call("GET", "/api/branches")[0] == 401:
        break
    time.sleep(2)
else:
    sys.exit("API did not become ready")
slug = "smoke-" + uuid.uuid4().hex[:10]
s, reg = call("POST", "/api/auth/register", {"companyName": "Smoke", "slug": slug, "ownerName": "Owner", "ownerPin": "1111"})
check("01 register tenant", s == 200, s)
H = {"Authorization": "Bearer " + reg["token"]}
s, staff = call("POST", "/api/staff", {"name": "Kassir", "role": "kassir", "pin": "2222"}, H)
s, login = call("POST", "/api/auth/login", {"company": slug, "pin": "2222"})
K = {"Authorization": "Bearer " + login["token"]}
check("02 staff RBAC: cashier cannot read audit", call("GET", "/api/audit", headers=K)[0] == 403)
s, branch = call("POST", "/api/branches", {"name": "Chilonzor"}, H)
main_id = call("GET", "/api/branches", headers=H)[1]["current"]
check("03 branch created", s == 201, branch)
s, inv = call("POST", "/api/inventories", {"lines": [{"ing": "beans", "counted": 2000}], "note": "smoke"}, H)
check("04 inventory count", s == 200, s)
s, shift = call("POST", "/api/shifts/open", {"openingCash": 100000}, H)
check("05 shift open", s == 200, s)
latte = [{"productId": "latte", "size": "M", "modIds": [], "qty": 2}]
s, partial = call("POST", "/api/orders", {"items": latte, "payment": "split", "allowPartial": True,
                                          "paymentParts": [{"method": "karta", "amount": 1000}], "clientKey": key()}, H)
check("06 partial split payment", s == 200 and partial.get("paymentStatus") in ("partial", "paid"), partial.get("paymentStatus") if isinstance(partial, dict) else partial)
if s == 200:
    rest = partial["total"] - 1000
    s, paid = call("POST", f"/api/orders/{partial['id']}/payments", {"method": "naqd", "amount": rest, "clientKey": key()}, H)
    check("07 settle remaining payment", s in (200, 201), s)
s, order = call("POST", "/api/orders", {"items": latte, "payment": "naqd", "clientKey": key()}, H)
check("08 cash order", s == 200, s)
s, refund = call("POST", f"/api/orders/{order['id']}/refunds", {"clientKey": key(), "amount": order["total"] // 2, "method": "naqd",
                                                                 "reason": "Smoke refund", "externalConfirmed": True}, H)
check("09 partial refund", s in (200, 201), s)
s, over = call("POST", f"/api/orders/{order['id']}/refunds", {"clientKey": key(), "amount": order["total"], "method": "naqd",
                                                               "reason": "Over refund", "externalConfirmed": True}, H)
check("10 over-refund rejected", s in (409, 422), s)
s, tr = call("POST", "/api/transfers", {"clientKey": key(), "toBranchId": branch["id"], "lines": [{"ing": "beans", "qty": 100}]}, H)
check("11 transfer dispatched", s in (200, 201), s)
s, _ = call("POST", f"/api/transfers/{tr['id']}/receive", {}, {**H, "X-Branch-Id": str(branch["id"])})
s2, _ = call("POST", f"/api/transfers/{tr['id']}/receive", {}, {**H, "X-Branch-Id": str(branch["id"])})
check("12 transfer received once", s == 200 and s2 == 409, (s, s2))
s, cfg = call("PUT", "/api/fiscal/config", {"tin": "123456789", "provider": "sandbox", "terminalId": "SMOKE-1", "enabled": True,
                                            "credentials": "smoke-secret"}, H)
check("13 fiscal sandbox config (secret hidden)", s == 200 and "smoke-secret" not in json.dumps(cfg), s)
s, fo = call("POST", "/api/orders", {"items": latte, "payment": "karta", "clientKey": key()}, H)
check("14 sandbox fiscal status", s == 200 and fo.get("fiscalStatus") == "sandbox", fo.get("fiscalStatus") if isinstance(fo, dict) else fo)
s, link = call("POST", f"/api/orders/{fo['id']}/receipt-link", None, H)
s, html = call("GET", link["path"], raw=True) if s == 200 else (s, "")
check("15 e-receipt marked non-fiscal sandbox", s == 200 and "SANDBOX" in html, s)
s, conflict = call("POST", "/api/orders", {"items": latte, "payment": "naqd", "offline": True, "clientKey": key(), "expectedTotal": 1}, H)
check("16 offline price conflict queued", s == 409 and conflict["detail"]["code"] == "offline_conflict", s)
s, dev = call("POST", "/api/devices", {"name": "Smoke POS", "branchId": branch["id"]}, H)
bound = {**K, "X-Device-Token": dev["token"]}
s1, br = call("GET", "/api/branches", headers=bound)
call("POST", f"/api/devices/{dev['id']}/revoke", {}, H)
s2, _ = call("GET", "/api/branches", headers=bound)
check("17 device binding + revoke", s1 == 200 and br["current"] == branch["id"] and s2 == 401, (s1, s2))
s, fin = call("GET", "/api/reports/finance?days=1", headers=H)
check("18 P&L includes refunds and COGS", s == 200 and fin["refunds"] > 0 and fin["revenue"] > 0 and "cogs" in fin, s)
s, _ = call("POST", "/api/shifts/close", {"closingCash": 100000}, H)
s, cv = call("GET", "/api/reports/cash-variance?days=1", headers=H)
check("19 cash variance report", s == 200 and len(cv["items"]) >= 1, s)
s, audit = call("GET", "/api/audit", headers=H)
actions = {e.get("action") for e in (audit.get("items", []) if isinstance(audit, dict) else [])}
check("20 audit trail", {"order.refund", "fiscal.config", "device.revoke"} <= actions, sorted(actions)[:12])
check("21 audit hides secrets", "smoke-secret" not in json.dumps(audit))
s, notes = call("GET", "/api/stock/notifications", headers={**H, "X-Branch-Id": str(main_id)})
check("22 low-stock endpoint", s == 200, s)
if len(sys.argv) > 2:
    adm = {"X-Superadmin-Key": sys.argv[2]}
    s, rel = call("POST", "/api/platform/releases", {"platform": "web", "version": f"5.{uuid.uuid4().int % 999}.0", "rolloutPercent": 100}, adm)
    s2, chk = call("GET", "/api/updates/check?platform=web&version=1.0.0", headers=H)
    s3, _ = call("POST", f"/api/platform/releases/{rel['id']}/rollback", {}, adm) if s == 201 else (s, None)
    check("23 release rollout + rollback", s == 201 and s2 == 200 and chk.get("update") and s3 == 200, (s, s2, s3))

width = max(len(n) for n, _, _ in results)
for name, ok, info in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {'' if ok else info}")
failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
