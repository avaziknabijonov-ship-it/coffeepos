"""Recorded refund audit and validation; no external payment processing."""
from uuid import uuid4

from fastapi.testclient import TestClient
from test_api import app, login


def company(client):
    slug = "refund-" + uuid4().hex[:12]
    result = client.post("/api/auth/register", json={
        "companyName": "Refund Test", "slug": slug,
        "ownerName": "Owner", "ownerPin": "1111",
    })
    assert result.status_code == 200, result.text
    return {"Authorization": f"Bearer {result.json()['token']}"}


def test_refund_limits_and_idempotency():
    with TestClient(app) as c:
        h = company(c)
        assert c.post("/api/shifts/open", json={"openingCash": 500000}, headers=h).status_code == 200
        order = c.post("/api/orders", json={
            "items": [{"productId": "latte", "size": "M", "qty": 1}],
            "payment": "split", "paymentParts": [
                {"method": "naqd", "amount": 10000},
                {"method": "karta", "amount": 20000},
            ], "cashGiven": 10000,
        }, headers=h)
        assert order.status_code == 200, order.text
        oid = order.json()["id"]
        url = f"/api/orders/{oid}/refunds"
        body = {"clientKey": "refund_" + uuid4().hex, "amount": 7000,
                "method": "naqd", "reason": "Mijozga qaytarildi",
                "externalConfirmed": True}
        assert c.post(url, json={**body, "externalConfirmed": False}, headers=h).status_code == 422
        assert c.post(url, json={**body, "method": "payme"}, headers=h).status_code == 422
        saved = c.post(url, json=body, headers=h)
        assert saved.status_code == 201, saved.text
        assert saved.json()["amount"] == 7000
        assert c.post(url, json=body, headers=h).json()["id"] == saved.json()["id"]
        assert c.post(url, json={**body, "amount": 7001}, headers=h).status_code == 409
        assert c.post(url, json={**body, "clientKey": "refund_" + uuid4().hex,
                                 "amount": 3001}, headers=h).status_code == 422
        assert c.post(url, json={**body, "clientKey": "refund_" + uuid4().hex,
                                 "amount": 3000}, headers=h).status_code == 201
        assert len(c.get(url, headers=h).json()) == 2
        assert c.get(url).status_code == 401
        assert c.get("/api/orders/999999/refunds", headers=h).status_code == 404


def test_refunds_tenant_isolation_and_cancellation():
    with TestClient(app) as c:
        h1, h2 = company(c), company(c)
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=h1).status_code == 200
        order = c.post("/api/orders", json={
            "items": [{"productId": "espresso", "size": "-", "qty": 1}],
            "payment": "karta",
        }, headers=h1)
        assert order.status_code == 200, order.text
        oid = order.json()["id"]
        url = f"/api/orders/{oid}/refunds"
        body = {"clientKey": "refund_" + uuid4().hex, "amount": 1000,
                "method": "karta", "reason": "Test refund", "externalConfirmed": True}
        assert c.get(url, headers=h2).status_code == 404
        assert c.post(url, json=body, headers=h2).status_code == 404
        assert c.post(f"/api/orders/{oid}/cancel", json={"reason": "Customer cancelled"},
                      headers=h1).status_code == 200
        assert c.post(url, json=body, headers=h1).status_code == 409
