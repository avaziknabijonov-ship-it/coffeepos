#!/usr/bin/env python3
"""Upgrade drill: seed a database with the legacy release, then start the current backend on it.

Usage: python scripts/migration_drill.py [--legacy-ref SHA] [--postgres ADMIN_URL]
Without --postgres a throwaway SQLite file is used. With --postgres a dedicated
`coffeepos_migration_drill` database is (re)created; only localhost URLs are accepted.
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LEGACY_REF = "29bad618a73d1b23cf8f296812fa88f7a273d40d"  # origin/main before the 23-module work
SLUG = "legacy-drill"

LEGACY = r'''
import json
from fastapi.testclient import TestClient
from app import seed
from app.main import app

def ok(r, *codes):
    assert r.status_code in (codes or (200,)), (r.request.method, r.request.url, r.status_code, r.text)
    return r.json()

with TestClient(app) as c:
    owner = {"Authorization": "Bearer " + ok(c.post("/api/auth/register", json={
        "companyName": "Legacy Cafe", "slug": "%(slug)s", "ownerName": "Owner", "ownerPin": "1111"}))["token"]}
    ok(c.post("/api/staff", json={"name": "Kassir A", "role": "kassir", "pin": "2222", "canCancelOrders": True}, headers=owner))
    cashier = {"Authorization": "Bearer " + ok(c.post("/api/auth/login", json={"company": "%(slug)s", "pin": "2222"}))["token"]}
    import time
    ok(c.post("/api/purchases", json={"number": "DRILL-1", "supplier": "Drill", "received_at": int(time.time() * 1000),
        "payment_status": "paid", "lines": [{"ing": key, "qty": 5000, "unit_price": 10} for key, *_ in seed.INGREDIENTS]}, headers=owner))
    ok(c.put("/api/bonus/config", json={"enabled": True, "earn_percent": 5, "redemption_limit_percent": 30}, headers=owner))
    ok(c.post("/api/shifts/open", json={"openingCash": 50000}, headers=cashier))
    latte = [{"productId": "latte", "size": "M", "modIds": [], "qty": 2}]
    orders = [ok(c.post("/api/orders", json={"items": latte, "payment": p, "clientKey": f"legacy-drill-{i:04d}",
                                            "customerPhone": "+998901112233" if p == "payme" else ""}, headers=cashier))
              for i, p in enumerate(["naqd", "karta", "payme", "naqd"])]
    ok(c.post(f"/api/orders/{orders[3]['id']}/cancel", json={"reason": "Mijoz voz kechdi"}, headers=cashier))
    ok(c.post("/api/expenses", json={"amount": 5000, "category": "Ijara", "payment": "cash"}, headers=owner))
    first = seed.INGREDIENTS[0][0]
    ok(c.post("/api/inventories", json={"lines": [{"ing": first, "counted": 4990}], "note": "drill"}, headers=owner))
    ok(c.post("/api/shifts/close", json={"closingCash": 60000}, headers=cashier))
    finance = ok(c.get("/api/reports/finance?days=30", headers=owner))
    bonus = ok(c.get("/api/bonus/customers/+998901112233", headers=owner))
    print("DRILL" + json.dumps({"orderIds": [o["id"] for o in orders], "totals": [o["total"] for o in orders],
                                "revenue": finance["revenue"], "orders": finance["orders"], "expenses": finance["expenses"],
                                "cogs": finance["cogs"], "bonus": bonus}))
'''

CURRENT = r'''
import json, sys
from fastapi.testclient import TestClient
from sqlalchemy import text
from app import migrations
from app.db import engine
from app.main import app

legacy = json.loads(sys.argv[1])
def ok(r, *codes):
    assert r.status_code in (codes or (200,)), (r.request.method, r.request.url, r.status_code, r.text)
    return r.json()
checks = []
def check(name, cond, detail=""):
    checks.append(name)
    assert cond, f"{name}: {detail}"
    print("  ok", name)

with TestClient(app) as c:
    with engine.connect() as db:
        q = lambda sql: db.execute(text(sql)).all()
        cid = q("SELECT id FROM companies WHERE slug = '%(slug)s'")[0][0]
        check("schema_migrations 1-8 recorded", sorted(r[0] for r in q("SELECT version FROM schema_migrations")) == [1, 2, 3, 4, 5, 6, 7, 8])
        check("default branch created", q(f"SELECT COUNT(*) FROM branches WHERE company_id = {cid} AND is_default = TRUE")[0][0] == 1)
        check("orders backfilled to branch", q(f"SELECT COUNT(*) FROM orders WHERE company_id = {cid} AND branch_id IS NULL")[0][0] == 0)
        check("shifts/expenses/stock moves backfilled", sum(q(f"SELECT COUNT(*) FROM {t} WHERE company_id = {cid} AND branch_id IS NULL")[0][0]
                                                        for t in ("shifts", "expenses", "stock_moves")) == 0)
        check("staff_id backfilled from unique names", q(f"SELECT COUNT(*) FROM orders WHERE company_id = {cid} AND staff_id IS NULL")[0][0] == 0)
        mismatched = q(f"""SELECT o.id FROM orders o WHERE o.company_id = {cid} AND o.total !=
            (SELECT COALESCE(SUM(p.amount), 0) FROM order_payments p WHERE p.order_id = o.id)""")
        check("legacy payments materialised (sum = total)", not mismatched, mismatched)
        check("legacy orders marked paid", q(f"SELECT COUNT(*) FROM orders WHERE company_id = {cid} AND payment_status != 'paid'")[0][0] == 0)
        check("legacy inventory approved", q(f"SELECT COUNT(*) FROM inventories WHERE company_id = {cid} AND status != 'approved'")[0][0] == 0)
    owner = {"Authorization": "Bearer " + ok(c.post("/api/auth/login", json={"company": "%(slug)s", "pin": "1111"}))["token"]}
    cashier = {"Authorization": "Bearer " + ok(c.post("/api/auth/login", json={"company": "%(slug)s", "pin": "2222"}))["token"]}
    fin = ok(c.get("/api/reports/finance?days=30", headers=owner))
    check("P&L revenue unchanged", fin["revenue"] == legacy["revenue"], (fin["revenue"], legacy["revenue"]))
    check("P&L orders/expenses/COGS unchanged", (fin["orders"], fin["expenses"], fin["cogs"]) ==
          (legacy["orders"], legacy["expenses"], legacy["cogs"]), (fin, legacy))
    bonus = ok(c.get("/api/bonus/customers/+998901112233", headers=owner))
    check("bonus balance unchanged", legacy["bonus"]["balance"] > 0 and bonus.get("balance") == legacy["bonus"]["balance"], (bonus, legacy["bonus"]))
    ok(c.post("/api/shifts/open", json={"openingCash": 10000}, headers=cashier))
    new = ok(c.post("/api/orders", json={"items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}],
                                         "payment": "naqd", "clientKey": "post-upgrade-0001"}, headers=cashier))
    check("new order after upgrade", new["total"] > 0)
    oid = legacy["orderIds"][0]
    ok(c.post(f"/api/orders/{oid}/refunds", json={"clientKey": "drill-refund-0001", "amount": 1000, "method": "naqd",
              "reason": "migration drill", "externalConfirmed": True}, headers=owner), 200, 201)
    check("partial refund of legacy order", True)
    over = c.post(f"/api/orders/{oid}/refunds", json={"clientKey": "drill-refund-0002", "amount": legacy["totals"][0],
                  "method": "naqd", "reason": "migration drill", "externalConfirmed": True}, headers=owner)
    check("over-refund of legacy order rejected", over.status_code in (400, 409, 422), over.text)
    check("re-running migrations is a no-op", migrations.run(engine) == [])
print(f"MIGRATION DRILL PASSED ({len(checks)} checks)")
'''


def local_only(url: str) -> None:
    if urlsplit(url.replace("+psycopg", "")).hostname not in ("127.0.0.1", "localhost"):
        sys.exit("refusing non-local database")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy-ref", default=LEGACY_REF)
    ap.add_argument("--postgres", help="local admin URL, e.g. postgresql+psycopg://u:p@127.0.0.1:5432/postgres")
    args = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix="coffeepos-drill-"))
    legacy = work / "legacy"
    if subprocess.run(["git", "cat-file", "-e", args.legacy_ref + "^{commit}"], cwd=ROOT).returncode:
        subprocess.run(["git", "fetch", "--depth=1", "origin", args.legacy_ref], cwd=ROOT, check=True)
    subprocess.run(["git", "worktree", "add", "--detach", str(legacy), args.legacy_ref], cwd=ROOT, check=True)
    try:
        if args.postgres:
            local_only(args.postgres)
            import psycopg
            with psycopg.connect(args.postgres.replace("+psycopg", ""), autocommit=True) as conn:
                conn.execute("DROP DATABASE IF EXISTS coffeepos_migration_drill")
                conn.execute("CREATE DATABASE coffeepos_migration_drill")
            url = args.postgres.rsplit("/", 1)[0] + "/coffeepos_migration_drill"
        else:
            url = f"sqlite:///{work / 'drill.db'}"
        env = {**os.environ, "DATABASE_URL": url, "ALLOW_PUBLIC_REGISTRATION": "1", "SEED_DEMO": "0"}
        env.pop("PYTHONPATH", None)
        print(f"legacy {args.legacy_ref[:8]} -> current on {url.split('@')[-1]}")
        out = subprocess.run([sys.executable, "-c", LEGACY % {"slug": SLUG}, "legacy"], cwd=legacy / "backend", env=env,
                             check=True, stdout=subprocess.PIPE, text=True).stdout
        data = next(line[5:] for line in out.splitlines() if line.startswith("DRILL"))
        print("legacy seed:", data)
        subprocess.run([sys.executable, "-c", CURRENT % {"slug": SLUG}, data], cwd=ROOT / "backend", env=env, check=True)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(legacy)], cwd=ROOT)


if __name__ == "__main__":
    main()
