"""G3: tables, Happy Hour caps/branches, loyalty reversal, customer erasure, staff analytics, combo returns."""
import time
from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from helpers import LATTE, at, new_company, staff_login
from test_api import app
from app.core import TZ


def key():
    return uuid4().hex


def test_floor_tables_move_merge_and_takeaway():
    with TestClient(app) as c:
        h, slug = new_company(c, "tbl")
        kassir, _ = staff_login(c, h, slug, "kassir", "1357")
        assert c.post("/api/areas", headers=kassir, json={"name": "Zal"}).status_code == 403
        area = c.post("/api/areas", headers=h, json={"name": "Zal"}).json()
        assert c.post("/api/areas", headers=h, json={"name": "Zal"}).status_code == 409
        t1 = c.post("/api/tables", headers=h, json={"areaId": area["id"], "name": "1", "seats": 4}).json()
        t2 = c.post("/api/tables", headers=h, json={"areaId": area["id"], "name": "2"}).json()
        items = LATTE["items"]
        assert c.post("/api/drafts", headers=kassir, json={"clientKey": key(), "items": items,
                                                          "service": "dine_in"}).status_code == 422
        a = c.post("/api/drafts", headers=kassir, json={"clientKey": key(), "items": items,
                                                       "service": "dine_in", "tableId": t1["id"]}).json()
        assert c.post("/api/drafts", headers=kassir, json={"clientKey": key(), "items": items,
                                                          "service": "dine_in", "tableId": t1["id"]}).status_code == 409
        b = c.post("/api/drafts", headers=kassir, json={"clientKey": key(), "items": items}).json()
        floor = c.get("/api/floor", headers=kassir).json()
        assert [t["occupied"] for t in floor["tables"]] == [True, False] and floor["takeaway"][0]["id"] == b["id"]
        moved = c.post(f"/api/drafts/{b['id']}/move", headers=kassir,
                       json={"version": b["version"], "tableId": t2["id"], "service": "dine_in"}).json()
        assert moved["tableId"] == t2["id"]
        assert c.post(f"/api/drafts/{b['id']}/move", headers=kassir,
                      json={"version": b["version"], "tableId": t1["id"]}).status_code == 409  # stale version
        assert c.post(f"/api/drafts/{b['id']}/move", headers=kassir,
                      json={"version": moved["version"], "tableId": t1["id"]}).status_code == 409  # occupied
        merge = {"version": moved["version"], "targetId": a["id"], "targetVersion": a["version"]}
        assert c.post(f"/api/drafts/{b['id']}/merge", headers=kassir, json=merge).status_code == 403
        merged = c.post(f"/api/drafts/{b['id']}/merge", headers=h, json=merge).json()
        assert len(merged["items"]) == 2 and len(c.get("/api/drafts", headers=h).json()) == 1
        assert c.put(f"/api/tables/{t1['id']}", headers=h, json={**t1, "areaId": area["id"],
                                                                "active": False}).status_code == 409
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        order = c.post("/api/orders", headers=h, json={"items": merged["items"], "payment": "karta",
                                                      "draftId": a["id"], "draftVersion": merged["version"]})
        assert order.status_code == 200, order.text
        assert order.json()["table"] == "1" and order.json()["service"] == "dine_in"
        assert c.get("/api/floor", headers=h).json()["tables"][0]["occupied"] is False
        other, _ = new_company(c, "tbx")
        assert c.post(f"/api/drafts/{a['id']}/move", headers=other, json={"version": 1}).status_code == 404
        second = c.post("/api/branches", json={"name": "B2"}, headers=h).json()["id"]
        assert c.get("/api/floor", headers=at(h, second)).json()["tables"] == []


def test_happy_hour_cap_and_branch_scope():
    with TestClient(app) as c:
        h, _ = new_company(c, "hh")
        second = c.post("/api/branches", json={"name": "B2"}, headers=h).json()["id"]
        now = datetime.now(TZ)
        start = f"{(now.hour - 1) % 24:02d}:00"
        end = f"{(now.hour + 2) % 24:02d}:00"
        base = {"name": "Kechki", "startTime": start, "endTime": end, "weekdays": list(range(7)), "percent": 50,
                "maxDiscount": 5000, "branchId": second}
        assert c.post("/api/promotions", headers=h, json={**base, "branchId": 99999}).status_code == 404
        assert c.post("/api/promotions", headers=h, json=base).status_code == 201
        assert c.get("/api/promotions/active", headers=h).json()["promotion"] is None
        assert c.get("/api/promotions/active", headers=at(h, second)).json()["promotion"]["maxDiscount"] == 5000
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=at(h, second))
        sale = {"items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 2}], "payment": "karta"}
        probe = c.post("/api/orders", headers=at(h, second), json=sale)
        assert probe.status_code == 409
        subtotal = c.post("/api/orders", headers=h, json={**sale, "expectedTotal": 0}).status_code  # no shift
        assert subtotal in (400, 409)
        ok = c.post("/api/orders", headers=at(h, second), json={**sale, "expectedTotal": 2 * 30000 - 5000})
        assert ok.status_code == 200, ok.text
        assert ok.json()["discount"] == 5000 and ok.json()["promotion"]["amount"] == 5000


def test_loyalty_refund_restores_redeemed_and_reverses_earned_with_consistent_ledger():
    with TestClient(app) as c:
        h, slug = new_company(c, "loy")
        assert c.put("/api/bonus/config", headers=h, json={
            "enabled": True, "earn_percent": 10, "redemption_limit_percent": 50}).status_code == 200
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        phone = "+998907770011"
        sale = {"items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}], "payment": "karta",
                "customerPhone": phone}
        first = c.post("/api/orders", headers=h, json=sale).json()
        earned = first["bonusEarned"]
        second = c.post("/api/orders", headers=h, json={**sale, "bonusRedeem": earned}).json()
        assert second["bonusUsed"] == earned
        refund = c.post(f"/api/orders/{second['id']}/refunds", headers=h, json={
            "clientKey": key(), "amount": second["total"], "method": "karta", "reason": "Qaytarildi",
            "externalConfirmed": True}).json()
        assert refund["bonusRestored"] == earned and refund["bonusReversed"] == second["bonusEarned"]
        customer = c.get("/api/customers", headers=h).json()["items"][0]
        ledger = c.get(f"/api/customers/{customer['id']}/bonus-ledger", headers=h).json()
        assert ledger["consistent"] and ledger["balance"] == earned
        assert {e["reason"] for e in ledger["items"]} == {"earn", "redeem", "refund_restore", "refund_reverse"}
        kassir, _ = staff_login(c, h, slug, "kassir", "2468")
        assert c.delete(f"/api/customers/{customer['id']}", headers=kassir).status_code == 403
        assert c.delete(f"/api/customers/{customer['id']}", headers=h).json()["erased"] is True
        assert c.get("/api/customers", headers=h).json()["items"] == []
        assert c.get(f"/api/bonus/customers/{phone}", headers=h).json()["balance"] == 0
        assert c.get(f"/api/customers/{customer['id']}/bonus-ledger", headers=h).status_code == 404
        orders = c.get(f"/api/orders?from_ms=0&to_ms={int(time.time() * 1000) + 1000}", headers=h)
        if orders.status_code == 200:
            assert all(o["customer"] == "" for o in orders.json()["items"] if isinstance(o, dict))
        audit = c.get("/api/audit?action=customer.erase", headers=h).json()["items"]
        assert len(audit) == 1 and phone not in str(audit)


def test_staff_self_report_and_branch_filter():
    with TestClient(app) as c:
        h, slug = new_company(c, "stf")
        kassir, kid = staff_login(c, h, slug, "kassir", "9753")
        second = c.post("/api/branches", json={"name": "B2"}, headers=h).json()["id"]
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=kassir)
        assert c.post("/api/orders", headers=kassir, json=LATTE).status_code == 200
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=at(h, second))
        assert c.post("/api/orders", headers=at(h, second), json=LATTE).status_code == 200
        now = int(time.time() * 1000)
        span = f"from_ms={now - 3600000}&to_ms={now + 3600000}"
        mine = c.get(f"/api/reports/staff/me?{span}", headers=kassir).json()
        assert mine["staffId"] == kid and mine["count"] == 1 and mine["shifts"] == 1
        assert c.get(f"/api/reports/staff?{span}", headers=kassir).status_code == 403
        rows = c.get(f"/api/reports/staff?{span}&branchId={second}", headers=h).json()["rows"]
        assert [r["name"] for r in rows] == ["Owner"] and rows[0]["count"] == 1
        assert len(c.get(f"/api/reports/staff?{span}", headers=h).json()["rows"]) == 2


def test_combo_item_refund_restocks_components_once():
    with TestClient(app) as c:
        h, _ = new_company(c, "cmb")
        menu = c.get("/api/menu", headers=h).json()
        combo = c.post("/api/combos", headers=h, json={
            "name": "Ikki latte", "cat": menu["products"][0]["cat"], "price": 50000,
            "components": [{"productId": "latte", "size": "M", "qty": 2},
                           {"productId": "espresso", "size": "-", "qty": 1}]})
        assert combo.status_code == 201, combo.text
        combo = combo.json()
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        before = c.get("/api/sync", headers=h).json()["stock"]
        order = c.post("/api/orders", headers=h, json={"items": [{"productId": combo["id"], "size": "-", "qty": 1}],
                                                      "payment": "karta"}).json()
        line = order["items"][0]
        refund = c.post(f"/api/orders/{order['id']}/refunds", headers=h, json={
            "clientKey": key(), "amount": order["total"], "method": "karta", "reason": "Qaytarildi",
            "externalConfirmed": True, "restock": True, "items": [{"key": line["key"], "qty": 1}]})
        assert refund.status_code == 201, refund.text
        assert c.get("/api/sync", headers=h).json()["stock"] == before
