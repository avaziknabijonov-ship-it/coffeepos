import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ["ALLOW_PUBLIC_REGISTRATION"] = "1"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.logic import promo_applies  # noqa: E402
from app.main import app  # noqa: E402

TZ = ZoneInfo("Asia/Tashkent")


def company(c, slug):
    r = c.post("/api/auth/register", json={"companyName": slug, "slug": slug, "ownerName": "Ega", "ownerPin": "1111"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


class P:
    def __init__(self, **kw):
        base = dict(active=True, date_from="", date_to="", days=[], start_time="00:00", end_time="00:00",
                    target="all", keys=[], pct=10, name="x")
        base.update(kw)
        self.__dict__.update(base)


def test_promo_time_windows():
    at = datetime(2026, 11, 27, 15, 30, tzinfo=TZ)  # Friday = weekday 4
    assert promo_applies(P(), "latte", "milk", at)
    assert promo_applies(P(start_time="15:00", end_time="17:00"), "latte", "milk", at)
    assert not promo_applies(P(start_time="16:00", end_time="17:00"), "latte", "milk", at)
    assert promo_applies(P(start_time="22:00", end_time="16:00"), "latte", "milk", at)  # overnight
    assert not promo_applies(P(days=[0, 1]), "latte", "milk", at)
    assert promo_applies(P(days=[4]), "latte", "milk", at)
    assert not promo_applies(P(date_to="2026-11-26"), "latte", "milk", at)
    assert not promo_applies(P(target="category", keys=["cold"]), "latte", "milk", at)
    assert promo_applies(P(target="product", keys=["latte"]), "latte", "milk", at)
    assert not promo_applies(P(active=False), "latte", "milk", at)


def test_promotions_reports_checklists_recurring():
    with TestClient(app) as c:
        h = company(c, "extra-kofe")
        assert c.post("/api/shifts/open", headers=h, json={"openingCash": 0}).status_code == 200
        today = datetime.now(TZ).weekday()

        bad = {"name": "X", "pct": 10, "target": "category", "keys": []}
        assert c.post("/api/promotions", headers=h, json=bad).status_code == 422
        assert c.post("/api/promotions", headers=h, json={**bad, "keys": ["nope"]}).status_code == 422
        r = c.post("/api/promotions", headers=h, json={"name": "Sutli -20%", "pct": 20, "target": "category", "keys": ["milk"]})
        assert r.status_code == 200, r.text
        # a weaker all-menu promo and one for another weekday never win over the 20% one
        c.post("/api/promotions", headers=h, json={"name": "Hammasi -5%", "pct": 5})
        other_day = (today + 1) % 7
        c.post("/api/promotions", headers=h, json={"name": "Ertaga -50%", "pct": 50, "days": [other_day]})
        menu = c.get("/api/menu", headers=h).json()
        assert len(menu["promotions"]) == 3

        order = {"items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 2},
                           {"productId": "espresso", "size": "-", "modIds": [], "qty": 1}],
                 "payment": "karta", "discountPct": 10}
        o = c.post("/api/orders", headers=h, json=order)
        assert o.status_code == 200, o.text
        o = o.json()
        latte, esp = o["items"]
        assert latte["promo"] == "Sutli -20%" and latte["promoDiscount"] == int(latte["unitPrice"] * 2 * 0.2 / 100 + 0.5) * 100
        assert esp["promo"] == "Hammasi -5%"
        promo = latte["promoDiscount"] + esp["promoDiscount"]
        manual = int((o["subtotal"] - promo) * 0.10 / 100 + 0.5) * 100
        assert o["discount"] == promo + manual and o["total"] == o["subtotal"] - o["discount"]

        # big manual discount and a self-cancel become risky receipts
        big = c.post("/api/orders", headers=h, json={**order, "discountPct": 30}).json()
        assert c.post(f"/api/orders/{big['id']}/cancel", headers=h, json={"reason": "test bekor"}).status_code == 200
        risky = c.get("/api/reports/risky", headers=h).json()
        flags = {r["id"]: r["flags"] for r in risky["receipts"]}
        assert "big_discount" in flags[big["id"]] and "cancelled" in flags[big["id"]] and "self_cancel" in flags[big["id"]]
        assert o["id"] not in flags

        sales = c.get("/api/reports/sales", headers=h).json()
        assert sales["totals"]["orders"] == 1 and sales["totals"]["cancelled"] == 1
        assert sales["totals"]["revenue"] == o["total"]
        assert sum(p["revenue"] for p in sales["products"]) in range(o["total"] - 2, o["total"] + 3)
        assert sales["products"][0]["abc"] == "A"
        assert c.get("/api/reports/sales?date_from=2026-01-01", headers=h).status_code == 400

        # checklists
        assert c.post("/api/checklists", headers=h, json={"name": "Ochish", "items": ["  "]}).status_code == 422
        cl = c.post("/api/checklists", headers=h, json={"name": "Ochish", "kind": "open", "items": ["Kofemashina", "Kassa"]}).json()
        assert c.post(f"/api/checklists/{cl['id']}/runs", headers=h, json={"done": [True]}).status_code == 422
        run = c.post(f"/api/checklists/{cl['id']}/runs", headers=h, json={"done": [True, False]}).json()
        assert run["done"] == 1 and run["total"] == 2 and run["shiftId"]
        assert c.get("/api/checklist-runs", headers=h).json()[0]["id"] == run["id"]

        # recurring payments become a single expense per month
        rp = c.post("/api/recurring", headers=h, json={"name": "Ijara", "amount": 5_000_000, "category": "Ijara", "day": 1}).json()
        assert rp["due"] is True and rp["paidThisMonth"] is False
        paid = c.post(f"/api/recurring/{rp['id']}/pay", headers=h, json={})
        assert paid.status_code == 200 and paid.json()["paidThisMonth"] is True
        assert c.post(f"/api/recurring/{rp['id']}/pay", headers=h, json={}).status_code == 409
        exp = c.get("/api/expenses", headers=h).json()
        assert any(e["amount"] == 5_000_000 and e["category"] == "Ijara" for e in exp)

        # isolation: another company cannot touch these rows
        h2 = company(c, "extra-kofe-2")
        assert c.put(f"/api/checklists/{cl['id']}", headers=h2, json={"name": "x", "items": ["y"]}).status_code == 404
        assert c.post(f"/api/recurring/{rp['id']}/pay", headers=h2, json={}).status_code == 404
        assert c.get("/api/promotions", headers=h2).json() == []
