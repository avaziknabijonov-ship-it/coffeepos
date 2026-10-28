from uuid import uuid4
from fastapi.testclient import TestClient
from test_api import app, login
from test_refunds_api import company


def test_staff_finance_permissions_and_isolation():
    with TestClient(app) as c:
        h, other = company(c), company(c)
        assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
        result = c.post('/api/orders', headers=h, json={
            'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}],
            'payment': 'karta', 'discountPct': 10,
        })
        assert result.status_code == 200, result.text
        order = result.json()
        refund = c.post(f"/api/orders/{order['id']}/refunds", headers=h, json={
            'clientKey': uuid4().hex, 'amount': 1000, 'method': 'karta',
            'reason': 'Staff report test', 'externalConfirmed': True,
        })
        assert refund.status_code == 201, refund.text
        params = {'from_ms': order['createdAt'] - 1000, 'to_ms': order['createdAt'] + 86400000}
        response = c.get('/api/reports/staff', params=params, headers=h)
        assert response.status_code == 200, response.text
        row = response.json()['rows'][0]
        assert row['count'] == 1 and row['shifts'] == 1
        assert row['revenue'] == order['total']
        assert row['discounts'] == order['discount']
        assert row['refunds'] == row['processedRefunds'] == 1000
        assert row['netRevenue'] == order['total'] - 1000
        assert row['byPayment'] == {'karta': order['total']}
        assert c.get('/api/reports/staff', params=params, headers=other).json()['rows'] == []
        assert c.get('/api/reports/staff', params=params).status_code == 401
        assert c.get('/api/reports/staff', params=params, headers=login(c, '2222')).status_code == 403
        assert c.get('/api/reports/staff', params={'from_ms': 10, 'to_ms': 9}, headers=h).status_code == 400
        assert c.get('/api/reports/staff', params={'from_ms': 0, 'to_ms': 367 * 86400000}, headers=h).status_code == 400
