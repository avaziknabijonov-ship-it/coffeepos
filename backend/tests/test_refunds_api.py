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
        assert c.post(url, json={**body, "reason": "   "}, headers=h).status_code == 422
        saved = c.post(url, json=body, headers=h)
        assert saved.status_code == 201, saved.text
        assert saved.json()["amount"] == 7000
        assert c.post(url, json=body, headers=h).json()["id"] == saved.json()["id"]
        assert c.post(f"/api/orders/{oid}/cancel", json={"reason": "Customer cancelled"},
                      headers=h).status_code == 409
        assert c.post(url, json={**body, "amount": 7001}, headers=h).status_code == 409
        assert c.post(url, json={**body, "clientKey": "refund_" + uuid4().hex,
                                 "amount": 3001}, headers=h).status_code == 422
        assert c.post(url, json={**body, "clientKey": "refund_" + uuid4().hex,
                                 "amount": 3000}, headers=h).status_code == 201
        assert len(c.get(url, headers=h).json()) == 2
        shift = c.get("/api/shifts/current", headers=h).json()
        assert shift["cashRefunds"] == 10000
        assert shift["expectedCash"] == 500000
        report = c.get("/api/reports/finance?days=1", headers=h).json()
        assert report["refunds"] == 10000
        assert report["refundsByPayment"]["naqd"] == 10000
        assert report["netRevenue"] == report["revenue"] - 10000
        assert report["daily"][-1]["refunds"] == 10000
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


def test_refund_today_for_historical_sale_is_reported_on_refund_date():
    from app.db import Order, SessionLocal

    with TestClient(app) as c:
        h = company(c)
        assert c.post('/api/shifts/open', json={'openingCash': 10000}, headers=h).status_code == 200
        response = c.post('/api/orders', headers=h, json={
            'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}], 'payment': 'karta',
        })
        assert response.status_code == 200, response.text
        order = response.json()
        # Historical sale, current-day refund: today's net cash revenue can be negative.
        with SessionLocal() as db:
            stored = db.get(Order, int(order['id']))
            stored.created_at -= 3 * 86400000
            db.commit()
        refund = c.post(f"/api/orders/{order['id']}/refunds", headers=h, json={
            'clientKey': uuid4().hex, 'amount': order['total'], 'method': 'karta',
            'reason': 'Historical sale refund', 'externalConfirmed': True,
        })
        assert refund.status_code == 201, refund.text
        report = c.get('/api/reports/finance?days=1', headers=h).json()
        assert report['revenue'] == 0
        assert report['refunds'] == order['total']
        assert report['netRevenue'] == -order['total']
        assert report['cogs'] == 0
        assert report['refundsByPayment'] == {'karta': order['total']}
        assert report['daily'][0]['netRevenue'] == report['netRevenue']
        period = c.get('/api/reports/finance?days=7', headers=h).json()
        assert period['netRevenue'] == 0
        assert sum(d['refunds'] for d in period['daily']) == order['total']
