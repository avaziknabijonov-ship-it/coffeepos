"""Acceptance protocol from docs/RELEASE_CHECKLIST_UZ.md, run against the real API."""
import itertools
import uuid

from fastapi.testclient import TestClient

from app.main import app

_seq = itertools.count()
_run = uuid.uuid4().hex[:6]
ORDER = {"items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}], "payment": "naqd"}


def tenant(c):
    n = next(_seq)
    r = c.post("/api/auth/register", json={"companyName": f"Accept {n}", "slug": f"accept-{_run}-{n:03d}",
                                           "ownerName": "Owner", "ownerPin": "1111"})
    assert r.status_code == 200, r.text
    slug = r.json()["company"]["slug"]
    owner = {"Authorization": "Bearer " + r.json()["token"]}

    def staff(name, role, pin, **flags):
        body = {"name": name, "role": role, "pin": pin, **flags}
        assert c.post("/api/staff", json=body, headers=owner).status_code == 200
        t = c.post("/api/auth/login", json={"company": slug, "pin": pin}).json()["token"]
        return {"Authorization": "Bearer " + t}

    return slug, owner, staff


def order(c, h, **extra):
    r = c.post("/api/orders", json={**ORDER, **extra}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def stock(c, h, key="beans"):
    return c.get("/api/sync", headers=h).json()["stock"][key]


def test_roles_and_dual_role():
    with TestClient(app) as c:
        _, owner, staff = tenant(c)
        kassir = staff("Kassir", "kassir", "2222")
        dual = staff("Dual", "kassir", "3333", canBarista=True)
        barista = staff("Barista", "barista", "4444")
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=kassir).status_code == 200
        o = order(c, kassir)
        assert c.post("/api/orders", json=ORDER, headers=barista).status_code == 403
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "preparing"}, headers=kassir).status_code == 403
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "preparing"}, headers=dual).status_code == 200
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "ready"}, headers=barista).status_code == 200
        for h in (kassir, barista, dual):
            assert c.get("/api/audit", headers=h).status_code == 403
            assert c.post(f"/api/orders/{o['id']}/refund", json={"reason": "test"}, headers=h).status_code == 403
            assert c.get("/api/reports/finance", headers=h).status_code == 403
        assert c.get("/api/audit", headers=owner).status_code == 200


def test_discount_boundaries():
    with TestClient(app) as c:
        _, owner, _ = tenant(c)
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=owner)
        base = order(c, owner)["subtotal"]
        for pct in (0, 17, 50):
            o = order(c, owner, discountPct=pct)
            assert o["discount"] == round(base * pct / 100 / 100) * 100
            assert o["total"] == o["subtotal"] - o["discount"]
        assert c.post("/api/orders", json={**ORDER, "discountPct": 51}, headers=owner).status_code == 422
        actions = [a["action"] for a in c.get("/api/audit?action=order.discount", headers=owner).json()["items"]]
        assert actions == ["order.discount", "order.discount"]


def test_shift_balance_with_expense_and_refund():
    with TestClient(app) as c:
        _, owner, _ = tenant(c)
        c.post("/api/shifts/open", json={"openingCash": 100000}, headers=owner)
        cash = order(c, owner)
        order(c, owner, payment="karta")
        assert c.post("/api/expenses", json={"amount": 5000, "category": "Suv", "payment": "cash"},
                      headers=owner).status_code == 200
        assert c.post(f"/api/orders/{cash['id']}/refund", json={"reason": "mijoz qaytardi"},
                      headers=owner).status_code == 200
        cur = c.get("/api/shifts/current", headers=owner).json()
        assert cur["refunds"] == cash["total"]
        assert cur["expectedCash"] == 100000 + cash["total"] - 5000 - cash["total"]
        closed = c.post("/api/shifts/close", json={"closingCash": cur["expectedCash"]}, headers=owner).json()
        assert closed["difference"] == 0


def test_refund_across_shifts_is_idempotent():
    with TestClient(app) as c:
        _, owner, _ = tenant(c)
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=owner)
        before = stock(c, owner)
        o = order(c, owner)
        for status in ("preparing", "ready", "done"):
            assert c.patch(f"/api/orders/{o['id']}", json={"status": status}, headers=owner).status_code == 200
        assert c.post(f"/api/orders/{o['id']}/cancel", json={"reason": "late"}, headers=owner).status_code == 409
        old = c.post("/api/shifts/close", json={"closingCash": o["total"]}, headers=owner).json()
        assert c.post(f"/api/orders/{o['id']}/refund", json={"reason": "late"}, headers=owner).status_code == 409
        c.post("/api/shifts/open", json={"openingCash": 50000}, headers=owner)
        r = c.post(f"/api/orders/{o['id']}/refund", json={"reason": "sovuq edi"}, headers=owner)
        assert r.status_code == 200 and r.json()["status"] == "refunded" and r.json()["refundedBy"] == "Owner"
        assert stock(c, owner) == before
        assert c.post(f"/api/orders/{o['id']}/refund", json={"reason": "again"}, headers=owner).status_code == 409
        assert stock(c, owner) == before
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "done"}, headers=owner).status_code == 409
        cur = c.get("/api/shifts/current", headers=owner).json()
        assert cur["expectedCash"] == 50000 - o["total"]
        history = c.get("/api/shifts", headers=owner).json()
        closed = next(s for s in history if s["shift"]["id"] == old["shift"]["id"])
        assert closed["revenue"] == o["total"] and closed["expectedCash"] == o["total"]
        fin = c.get("/api/reports/finance?days=1", headers=owner).json()
        assert fin["revenue"] == 0 and fin["orders"] == 0
        refund_log = c.get("/api/audit?action=order.refund", headers=owner).json()["items"]
        assert len(refund_log) == 1 and refund_log[0]["details"]["previousStatus"] == "done"


def test_refund_without_restock_keeps_stock():
    with TestClient(app) as c:
        _, owner, _ = tenant(c)
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=owner)
        o = order(c, owner)
        after_sale = stock(c, owner)
        r = c.post(f"/api/orders/{o['id']}/refund", json={"reason": "tayyorlangan", "restock": False}, headers=owner)
        assert r.status_code == 200
        assert stock(c, owner) == after_sale


def test_client_key_and_cancel_idempotency():
    with TestClient(app) as c:
        _, owner, _ = tenant(c)
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=owner)
        before = stock(c, owner)
        first = order(c, owner, clientKey="tablet-a-000000001")
        again = order(c, owner, clientKey="tablet-a-000000001")
        assert first["id"] == again["id"]
        used = before - stock(c, owner)
        assert used > 0
        assert c.post(f"/api/orders/{first['id']}/cancel", json={"reason": "xato"}, headers=owner).status_code == 200
        assert stock(c, owner) == before
        assert c.post(f"/api/orders/{first['id']}/cancel", json={"reason": "xato"}, headers=owner).status_code == 409
        assert stock(c, owner) == before


def test_bonus_reversal_on_refund():
    with TestClient(app) as c:
        _, owner, _ = tenant(c)
        assert c.put("/api/bonus/config", json={"enabled": True, "earn_percent": 10,
                                                "redemption_limit_percent": 50}, headers=owner).status_code == 200
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=owner)
        o = order(c, owner, customerPhone="998901234567")
        bal = c.get("/api/bonus/customers/998901234567", headers=owner).json()["balance"]
        assert bal == o["bonusEarned"] > 0
        assert c.post(f"/api/orders/{o['id']}/refund", json={"reason": "qaytdi"}, headers=owner).status_code == 200
        assert c.get("/api/bonus/customers/998901234567", headers=owner).json()["balance"] == 0


def test_two_tenants_are_isolated():
    with TestClient(app) as c:
        _, a, _ = tenant(c)
        _, b, _ = tenant(c)
        for h in (a, b):
            c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        c.put("/api/bonus/config", json={"enabled": True, "earn_percent": 5, "redemption_limit_percent": 30}, headers=a)
        o = order(c, a, customerPhone="998909999999")
        assert c.post(f"/api/orders/{o['id']}/refund", json={"reason": "hack"}, headers=b).status_code == 404
        assert c.post(f"/api/orders/{o['id']}/cancel", json={"reason": "hack"}, headers=b).status_code == 404
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "preparing"}, headers=b).status_code == 404
        assert all(x["id"] != o["id"] for x in c.get("/api/sync", headers=b).json()["orders"])
        assert c.get("/api/bonus/customers/998909999999", headers=b).json()["balance"] == 0
        a_log = c.get("/api/audit", headers=a).json()["items"]
        b_log = c.get("/api/audit", headers=b).json()["items"]
        assert {x["id"] for x in a_log}.isdisjoint({x["id"] for x in b_log})
        assert not any(x["action"] == "bonus.config" for x in b_log)


def test_two_tablets_send_same_order_concurrently():
    from concurrent.futures import ThreadPoolExecutor

    with TestClient(app) as c:
        _, owner, staff = tenant(c)
        tablets = [owner, staff("Tablet2", "kassir", "5555")]
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=owner)
        before = stock(c, owner)
        body = {**ORDER, "clientKey": "offline-queue-0000042"}
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda i: c.post("/api/orders", json=body, headers=tablets[i % 2]), range(8)))
        ok = [r.json()["id"] for r in results if r.status_code == 200]
        assert ok and len(set(ok)) == 1, [(r.status_code, r.text) for r in results]
        assert all(r.status_code in (200, 409) for r in results)
        orders = [o for o in c.get("/api/sync", headers=owner).json()["orders"] if o["id"] == ok[0]]
        assert len(orders) == 1
        assert c.get("/api/shifts/current", headers=owner).json()["orders"] == 1
        # Stock was consumed exactly once: cancelling the single order restores the start level.
        assert c.post(f"/api/orders/{ok[0]}/cancel", json={"reason": "check"}, headers=owner).status_code == 200
        assert stock(c, owner) == before
