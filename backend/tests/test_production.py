import os
import tempfile

os.environ["ALLOW_PUBLIC_REGISTRATION"] = "1"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")

from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402
from app.main import app  # noqa: E402


def company(c, slug):
    r = c.post("/api/auth/register", json={"companyName": slug, "slug": slug, "ownerName": "Ega", "ownerPin": "1111"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def buy(c, h, number, lines):
    r = c.post("/api/purchases", headers=h, json={
        "number": number, "supplier": "Bozor", "received_at": 1780000000000, "payment_status": "paid",
        "lines": [{"ing": ing, "qty": qty, "unit_price": price} for ing, qty, price in lines],
    })
    assert r.status_code == 200, r.text


def stock(c, h):
    return c.get("/api/sync", headers=h).json()["stock"]


def test_semi_finished_production_and_sale():
    with TestClient(app) as c:
        h = company(c, "semi-kofe")
        buy(c, h, "N1", [("syr-caramel", 1000, 100), ("milk", 1000, 10)])

        # 1 batch = 500 ml of caramel cream from 200 ml syrup + 400 ml milk
        body = {"name": "Karamel krem", "unit": "ml", "cost": 0, "min": 100,
                "recipe": [{"ing": "syr-caramel", "qty": 200}, {"ing": "milk", "qty": 400}], "yieldQty": 500}
        r = c.post("/api/ingredients", headers=h, json=body)
        assert r.status_code == 200, r.text
        semi = r.json()
        assert semi["semi"] and semi["yieldQty"] == 500
        assert abs(semi["cost"] - (200 * 100 + 400 * 10) / 500) < 1e-6

        # nested semi and self-reference are refused
        nested = {**body, "name": "Ikki qavat", "recipe": [{"ing": semi["id"], "qty": 10}]}
        assert c.post("/api/ingredients", headers=h, json=nested).status_code == 400
        assert c.put(f"/api/ingredients/{semi['id']}", headers=h,
                     json={**body, "recipe": [{"ing": semi["id"], "qty": 1}]}).status_code == 400
        # missing yield
        assert c.post("/api/ingredients", headers=h, json={**body, "name": "X", "yieldQty": 0}).status_code == 400

        # production: 250 ml = half a batch
        r = c.post("/api/production", headers=h, json={"ing": semi["id"], "qty": 250})
        assert r.status_code == 200, r.text
        s = stock(c, h)
        assert s[semi["id"]] == 250
        assert s["syr-caramel"] == 900 and s["milk"] == 800
        # raw ingredient can't be "produced"
        assert c.post("/api/production", headers=h, json={"ing": "milk", "qty": 10}).status_code == 400

        moves = c.get("/api/stock/moves", headers=h).json()
        reasons = {(m["ing"], m["reason"]) for m in moves}
        assert (semi["id"], "production") in reasons and ("milk", "prod_use") in reasons

        # a component used in a semi recipe can't be deleted or turned into a semi itself
        milk = next(i for i in c.get("/api/menu", headers=h).json()["ingredients"] if i["id"] == "milk")
        assert c.put("/api/ingredients/milk", headers=h, json={
            "name": milk["name"], "unit": "ml", "cost": 10, "min": 0,
            "recipe": [{"ing": "beans", "qty": 1}], "yieldQty": 1}).status_code == 409


def test_auto_stoplist_and_low_stock_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(main, "send_low_stock_alert", lambda token, chat, name, crossed: sent.append(crossed))
    with TestClient(app) as c:
        h = company(c, "stop-kofe")
        assert c.post("/api/shifts/open", headers=h, json={"openingCash": 0}).status_code == 200
        espresso = {"items": [{"productId": "espresso", "size": "-", "modIds": [], "qty": 1}], "payment": "karta"}

        # default: stop-list off, selling with empty stock is still allowed (old behaviour)
        assert c.get("/api/menu", headers=h).json()["settings"] == {"autoStoplist": False}
        assert c.post("/api/orders", headers=h, json=espresso).status_code == 200

        cfg = c.put("/api/stock/config", headers=h, json={
            "autoStoplist": True, "telegramChat": "-100123", "telegramToken": "123456:" + "A" * 30})
        assert cfg.status_code == 200, cfg.text
        assert cfg.json() == {"autoStoplist": True, "telegramChat": "-100123", "telegramConfigured": True}
        assert "telegramToken" not in c.get("/api/stock/config", headers=h).json()
        assert c.get("/api/menu", headers=h).json()["settings"] == {"autoStoplist": True}

        r = c.post("/api/orders", headers=h, json=espresso)
        assert r.status_code == 409 and "stop-list" in r.json()["detail"]
        # offline sales replayed later are never refused
        assert c.post("/api/orders", headers=h, json={**espresso, "offline": True}).status_code == 200

        # fill stock above minimum, then sell until beans cross below the minimum
        menu = c.get("/api/menu", headers=h).json()
        recipe = next(p for p in menu["products"] if p["id"] == "espresso")["sizes"][0]["recipe"]
        beans_per_cup = next(l["qty"] for l in recipe if l["ing"] == "beans")
        beans_min = next(i for i in menu["ingredients"] if i["id"] == "beans")["min"]
        s = stock(c, h)
        need = {l["ing"]: 0 for l in recipe}
        buy(c, h, "N2", [(ing, (beans_min + beans_per_cup if ing == "beans" else 50) - s[ing], 100) for ing in need])
        sent.clear()
        assert c.post("/api/orders", headers=h, json=espresso).status_code == 200
        assert c.post("/api/orders", headers=h, json=espresso).status_code == 200
        assert any(any(x["name"].startswith("Kofe") for x in crossed) for crossed in sent)

        # token can be removed; keeping it requires sending null
        cfg = c.put("/api/stock/config", headers=h, json={"autoStoplist": False, "telegramChat": "-100123", "telegramToken": ""})
        assert cfg.json()["telegramConfigured"] is False
        assert c.put("/api/stock/config", headers=h, json={"autoStoplist": False, "telegramToken": "bad"}).status_code == 422
