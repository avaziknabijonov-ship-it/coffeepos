import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def login(c, pin, company="demo"):
    r = c.post("/api/auth/login", json={"company": company, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_full_flow():
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"company": "demo", "pin": "9999"}).status_code == 401
        owner, kassir, barista = login(c, "1111"), login(c, "2222"), login(c, "3333")

        menu = c.get("/api/menu", headers=kassir).json()
        assert len(menu["products"]) == 17
        beans_before = next(i for i in menu["ingredients"] if i["id"] == "beans")["stock"]
        almond_before = next(i for i in menu["ingredients"] if i["id"] == "almond")["stock"]

        order = {"items": [{"productId": "latte", "size": "M", "modIds": ["milk-almond", "shot1"], "qty": 2}],
                 "customer": "Aziz", "payment": "naqd", "cashGiven": 100000}
        assert c.post("/api/orders", json=order, headers=kassir).status_code == 409
        assert c.post("/api/shifts/open", json={"openingCash": 200000}, headers=barista).status_code == 403
        assert c.post("/api/shifts/open", json={"openingCash": 200000}, headers=kassir).status_code == 200

        r = c.post("/api/orders", json=order, headers=kassir)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["number"] == 1 and o["total"] == 2 * (30000 + 6000 + 5000)
        assert o["items"][0]["mods"] == ["Bodom suti", "+1 shot"]

        stock = c.get("/api/sync", headers=barista).json()["stock"]
        assert stock["beans"] == beans_before - 2 * (18 + 9)
        assert stock["almond"] == almond_before - 2 * 240

        bad = {**order, "items": [{"productId": "espresso", "size": "-", "modIds": ["milk-almond"]}]}
        assert c.post("/api/orders", json=bad, headers=kassir).status_code == 400

        assert c.patch(f"/api/orders/{o['id']}", json={"status": "ready"}, headers=barista).json()["readyAt"]

        assert c.patch("/api/products/latte/active", json={"active": False}, headers=kassir).status_code == 200
        assert c.post("/api/orders", json=order, headers=kassir).status_code == 400

        assert c.get("/api/staff", headers=kassir).status_code == 403
        assert c.post("/api/staff", json={"name": "X", "role": "barista", "pin": "2222"}, headers=owner).status_code == 409
        assert c.post("/api/staff", json={"name": "Lola", "role": "barista", "pin": "4444"}, headers=owner).status_code == 200
        login(c, "4444")

        r = c.post("/api/stock", json={"ing": "beans", "qty": 1000, "reason": "intake"}, headers=owner)
        assert r.json()["stock"] == stock["beans"] + 1000

        closed = c.post("/api/shifts/close", json={"closingCash": 282000}, headers=kassir).json()
        assert closed["expectedCash"] == 200000 + 82000 and closed["difference"] == 0
        assert c.get("/api/reports/daily", headers=owner).json()[-1]["revenue"] == 82000


def test_register_is_isolated():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"companyName": "Bek Kofe", "slug": "bek-kofe", "ownerName": "Bek", "ownerPin": "1111"})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert r.json()["staff"]["role"] == "owner"
        assert c.get("/api/sync", headers=h).json()["orders"] == []
        assert c.post("/api/auth/register", json={"companyName": "Boshqa", "slug": "bek-kofe", "ownerName": "Vali", "ownerPin": "2222"}).status_code == 409
