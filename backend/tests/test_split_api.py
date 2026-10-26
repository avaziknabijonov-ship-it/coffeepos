"""Integration coverage: split tenders, shift reconciliation and finance allocation."""
from uuid import uuid4

from fastapi.testclient import TestClient
from test_api import app, login


def test_split_tender_and_reports():
    with TestClient(app) as c:
        slug = "split-" + uuid4().hex[:12]
        registered = c.post("/api/auth/register", json={
            "companyName": "Split Test", "slug": slug,
            "ownerName": "Owner", "ownerPin": "1111",
        })
        assert registered.status_code == 200, registered.text
        h = {"Authorization": f"Bearer {registered.json()['token']}"}
        assert c.post("/api/shifts/open", json={"openingCash": 10000}, headers=h).status_code == 200
        menu = c.get("/api/menu", headers=h).json()
        product = next(p for p in menu["products"] if p["active"])
        size = product["sizes"][0]["code"]
        price = product["sizes"][0]["price"]
        assert price > 1
        half = price // 2
        order = {
            "items": [{"productId": product["id"], "size": size, "qty": 1}],
            "payment": "split",
            "paymentParts": [{"method": "naqd", "amount": half},
                             {"method": "karta", "amount": price - half}],
            "cashGiven": half,
        }
        for invalid in (
            {**order, "paymentParts": [{"method": "naqd", "amount": half}]},
            {**order, "paymentParts": [{"method": "naqd", "amount": half},
                                     {"method": "naqd", "amount": price - half}]},
            {**order, "paymentParts": [{"method": "naqd", "amount": half},
                                     {"method": "karta", "amount": price - half + 1}]},
            {**order, "cashGiven": half - 1},
            {**order, "payment": "naqd"},
        ):
            assert c.post("/api/orders", json=invalid, headers=h).status_code in (400, 422)
        saved = c.post("/api/orders", json=order, headers=h)
        assert saved.status_code == 200, saved.text
        assert saved.json()["payment"] == "split"
        assert saved.json()["paymentParts"] == order["paymentParts"]
        shift = c.get("/api/shifts/current", headers=h).json()
        assert shift["byPayment"]["naqd"] == half
        assert shift["byPayment"]["karta"] == price - half
        assert shift["expectedCash"] == 10000 + half
        finance = c.get("/api/reports/finance?days=1", headers=h).json()
        assert finance["byPayment"]["naqd"] == half
        assert finance["byPayment"]["karta"] == price - half
        closed = c.post("/api/shifts/close", json={"closingCash": 10000 + half}, headers=h)
        assert closed.status_code == 200, closed.text
        assert closed.json()["difference"] == 0


def test_legacy_single_tender():
    with TestClient(app) as c:
        owner = login(c, "1111")
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=owner).status_code in (200, 409)
        response = c.post("/api/orders", json={
            "items": [{"productId": "espresso", "size": "-", "qty": 1}],
            "payment": "karta",
        }, headers=owner)
        assert response.status_code == 200, response.text
        assert response.json()["paymentParts"] == [{"method": "karta", "amount": response.json()["total"]}]
