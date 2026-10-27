"""Tenant-isolated inventory threshold alerts."""
from uuid import uuid4

from fastapi.testclient import TestClient
from test_api import app, login


def new_company(client):
    slug = "alerts-" + uuid4().hex[:12]
    response = client.post("/api/auth/register", json={
        "companyName": "Alert Test", "slug": slug,
        "ownerName": "Owner", "ownerPin": "1111",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_low_stock_alert_threshold_and_receiving():
    with TestClient(app) as c:
        h = new_company(c)
        initial = c.get("/api/stock/alerts", headers=h)
        assert initial.status_code == 200, initial.text
        alerts = initial.json()
        assert alerts["count"] == len(alerts["items"])
        beans = next(x for x in alerts["items"] if x["id"] == "beans")
        assert beans["stock"] == 0
        assert beans["min"] > 0
        assert beans["shortfall"] == beans["min"]
        # Exactly at the minimum is still an alert.
        received = c.post("/api/purchases", json={
            "number": "LOW-1", "supplier": "Supplier", "received_at": 1780000000000,
            "payment_status": "paid",
            "lines": [{"ing": "beans", "qty": beans["min"], "unit_price": 100}],
        }, headers=h)
        assert received.status_code == 200, received.text
        at_min = c.get("/api/stock/alerts", headers=h).json()
        current = next(x for x in at_min["items"] if x["id"] == "beans")
        assert current["stock"] == current["min"]
        assert current["shortfall"] == 0
        # Receiving more removes the alert immediately.
        received = c.post("/api/purchases", json={
            "number": "LOW-2", "supplier": "Supplier", "received_at": 1780000000000,
            "payment_status": "paid",
            "lines": [{"ing": "beans", "qty": 1, "unit_price": 100}],
        }, headers=h)
        assert received.status_code == 200, received.text
        assert "beans" not in {x["id"] for x in c.get("/api/stock/alerts", headers=h).json()["items"]}
        # A zero threshold means alerts are disabled, not every empty ingredient is urgent.
        ingredient = next(i for i in c.get("/api/menu", headers=h).json()["ingredients"] if i["id"] == "beans")
        updated = c.put("/api/ingredients/beans", json={
            "name": ingredient["name"], "unit": ingredient["unit"],
            "cost": ingredient["cost"], "min": 0,
        }, headers=h)
        assert updated.status_code == 200, updated.text
        assert "beans" not in {x["id"] for x in c.get("/api/stock/alerts", headers=h).json()["items"]}


def test_stock_alerts_are_private_to_company_and_managers():
    with TestClient(app) as c:
        h1 = new_company(c)
        h2 = new_company(c)
        a = c.get("/api/stock/alerts", headers=h1).json()
        b = c.get("/api/stock/alerts", headers=h2).json()
        assert a == b
        assert c.get("/api/stock/alerts").status_code == 401
        kassir = login(c, "2222")
        assert c.get("/api/stock/alerts", headers=kassir).status_code == 403
        assert c.post("/api/purchases", json={
            "number": "LOW-ISOLATION", "supplier": "Supplier", "received_at": 1780000000000,
            "payment_status": "paid",
            "lines": [{"ing": "beans", "qty": 999999, "unit_price": 100}],
        }, headers=h1).status_code == 200
        assert c.get("/api/stock/alerts", headers=h2).json() == b
