"""G1: tender ledger, partial payments, item refunds with reversals, drafts, P&L and cash variance."""
from uuid import uuid4

from fastapi.testclient import TestClient

from helpers import LATTE, at, new_company, staff_login
from test_api import app


def key():
    return uuid4().hex


def test_partial_payment_settlement_is_idempotent_and_counted_once():
    with TestClient(app) as c:
        h, slug = new_company(c, "pay")
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=h).status_code == 200
        r = c.post("/api/orders", headers=h, json={**LATTE, "payment": "split", "allowPartial": True,
                                                  "paymentParts": [{"method": "naqd", "amount": 10000}]})
        assert r.status_code == 200, r.text
        order = r.json()
        assert order["paymentStatus"] == "partial" and order["outstanding"] == order["total"] - 10000
        url = f"/api/orders/{order['id']}/payments"
        assert c.post(url, headers=h, json={"clientKey": key(), "method": "karta",
                                            "amount": order["outstanding"] + 1}).status_code == 422
        pay = {"clientKey": key(), "method": "karta", "amount": order["outstanding"]}
        first = c.post(url, headers=h, json=pay)
        assert first.status_code == 201 and first.json()["paymentStatus"] == "paid"
        assert c.post(url, headers=h, json=pay).json()["paid"] == order["total"]  # retry / second device
        assert c.post(url, headers=h, json={**pay, "clientKey": key()}).status_code == 409
        assert c.post(url, headers=h, json={**pay, "amount": 1}).status_code == 409  # key reuse, other payload
        summary = c.get("/api/shifts/current", headers=h).json()
        assert summary["byPayment"] == {"naqd": 10000, "karta": order["total"] - 10000}
        finance = c.get("/api/reports/finance?days=1", headers=h).json()
        assert finance["reconciliation"]["collected"] == order["total"]
        assert finance["reconciliation"]["outstanding"] == 0
        assert c.post("/api/orders", headers=h, json={**LATTE, "allowPartial": True}).status_code == 422
        barista, _ = staff_login(c, h, slug, "barista", "3456")
        assert c.post(url, headers=barista, json={**pay, "clientKey": key()}).status_code == 403


def test_item_refund_restocks_reverses_cost_and_bonus_without_over_return():
    with TestClient(app) as c:
        h, _ = new_company(c, "ref")
        assert c.put("/api/bonus/config", headers=h, json={
            "enabled": True, "earn_percent": 10, "redemption_limit_percent": 30}).status_code == 200
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=h).status_code == 200
        before = c.get("/api/sync", headers=h).json()["stock"]["beans"]
        sale = {"items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 2}], "payment": "karta",
                "customerPhone": "+998901112233"}
        order = c.post("/api/orders", headers=h, json=sale).json()
        line = order["items"][0]
        assert c.get("/api/sync", headers=h).json()["stock"]["beans"] < before
        url = f"/api/orders/{order['id']}/refunds"
        base = {"method": "karta", "reason": "Mijoz qaytardi", "externalConfirmed": True}
        assert c.post(url, headers=h, json={**base, "clientKey": key(), "amount": 1000,
                                            "restock": True}).status_code == 422
        assert c.post(url, headers=h, json={**base, "clientKey": key(), "amount": line["unitPrice"] + 1,
                                            "items": [{"key": line["key"], "qty": 1}]}).status_code == 422
        body = {**base, "clientKey": key(), "amount": line["unitPrice"], "restock": True,
                "items": [{"key": line["key"], "qty": 1}]}
        refund = c.post(url, headers=h, json=body)
        assert refund.status_code == 201, refund.text
        data = refund.json()
        assert data["costReversed"] == line["unitCost"] and data["restocked"] is True
        assert data["bonusReversed"] == order["bonusEarned"] // 2 and data["fiscalStatus"] == "nonfiscal"
        assert c.post(url, headers=h, json=body).json()["id"] == data["id"]
        assert c.post(url, headers=h, json={**body, "restock": False}).status_code == 409
        beans_used = next(u["qty"] for u in line["consumption"] if u["ing"] == "beans")
        assert c.get("/api/sync", headers=h).json()["stock"]["beans"] == before - beans_used
        assert c.post(url, headers=h, json={**body, "clientKey": key(), "amount": 1,
                                            "items": [{"key": line["key"], "qty": 2}]}).status_code == 422
        customer = c.get("/api/bonus/customers/+998901112233", headers=h).json()
        assert customer["balance"] == order["bonusEarned"] - data["bonusReversed"]
        finance = c.get("/api/reports/finance?days=1", headers=h).json()
        assert finance["cogs"] == order["cost"] - line["unitCost"]
        assert finance["netRevenue"] == order["total"] - line["unitPrice"]


def test_draft_checkout_is_atomic_and_version_checked():
    with TestClient(app) as c:
        h, _ = new_company(c, "drf")
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=h).status_code == 200
        draft = c.post("/api/drafts", headers=h, json={"clientKey": key(), "items": LATTE["items"]}).json()
        assert c.get("/api/reports/finance?days=1", headers=h).json()["revenue"] == 0
        stale = {**LATTE, "draftId": draft["id"], "draftVersion": draft["version"] + 1}
        assert c.post("/api/orders", headers=h, json=stale).status_code == 409
        ok = c.post("/api/orders", headers=h, json={**stale, "draftVersion": draft["version"]})
        assert ok.status_code == 200
        assert c.get("/api/drafts", headers=h).json() == []
        assert c.post("/api/orders", headers=h, json={**stale, "draftVersion": draft["version"]}).status_code == 404


def test_branch_pnl_and_cash_variance_with_actor():
    with TestClient(app) as c:
        h, slug = new_company(c, "pnl")
        second = c.post("/api/branches", json={"name": "Yunusobod"}, headers=h).json()["id"]
        for branch, opening in ((None, 1000), (second, 2000)):
            hh = at(h, branch) if branch else h
            assert c.post("/api/shifts/open", json={"openingCash": opening}, headers=hh).status_code == 200
            assert c.post("/api/orders", headers=hh, json=LATTE).status_code == 200
        assert c.post("/api/expenses", headers=at(h, second), json={
            "amount": 500, "category": "Suv", "description": "", "payment": "cash"}).status_code == 200
        all_view = c.get("/api/reports/finance?days=1", headers=h).json()
        branch_view = c.get(f"/api/reports/finance?days=1&branchId={second}", headers=h).json()
        assert branch_view["revenue"] * 2 == all_view["revenue"] and branch_view["expenses"] == 500
        assert all_view["operatingBalance"] == all_view["netRevenue"] - all_view["cogs"] - 500
        current = c.get("/api/shifts/current", headers=at(h, second)).json()
        closed = c.post("/api/shifts/close", headers=at(h, second),
                        json={"closingCash": current["expectedCash"] - 300})
        assert closed.json()["difference"] == -300
        report = c.get(f"/api/reports/cash-variance?branchId={second}", headers=h).json()
        row = report["items"][0]
        assert row["expectedCash"] == 2000 + row["cashSales"] - 500 and row["difference"] == -300
        assert row["closedBy"] == "Owner" and report["shortage"] == 300
        audit = c.get("/api/audit?action=shift.close", headers=h).json()["items"][0]
        assert audit["after"]["difference"] == -300 and audit["actor"] == "Owner"
        kassir, kid = staff_login(c, h, slug, "kassir", "7531")
        assert c.get("/api/reports/cash-variance", headers=kassir).status_code == 403
        admin, aid = staff_login(c, h, slug, "admin", "8642")
        assert c.put(f"/api/staff/{aid}/branch", json={"branchId": second}, headers=h).status_code == 200
        main_branch = c.get("/api/branches", headers=h).json()["current"]
        assert c.get(f"/api/reports/finance?branchId={main_branch}", headers=admin).status_code == 403
