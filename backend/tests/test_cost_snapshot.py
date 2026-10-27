"""Historical COGS must not change when a manager edits current ingredient costs."""
from fastapi.testclient import TestClient
from test_api import app
from test_refunds_api import company


def test_order_cost_and_finance_are_historical_snapshots():
    with TestClient(app) as c:
        h = company(c)
        assert c.post('/api/shifts/open', json={'openingCash': 0}, headers=h).status_code == 200
        for item in c.get('/api/menu', headers=h).json()['ingredients']:
            assert c.put('/api/ingredients/' + item['id'], headers=h, json={
                'name': item['name'], 'unit': item['unit'], 'cost': 100, 'min': item['min'],
            }).status_code == 200
        body = {'items': [{'productId': 'latte', 'size': 'M', 'qty': 2}], 'payment': 'karta'}
        response = c.post('/api/orders', json=body, headers=h)
        assert response.status_code == 200, response.text
        original = response.json()
        assert original['cost'] > 0
        finance_before = c.get('/api/reports/finance?days=1', headers=h).json()
        for item in c.get('/api/menu', headers=h).json()['ingredients']:
            updated = c.put('/api/ingredients/' + item['id'], headers=h, json={
                'name': item['name'], 'unit': item['unit'], 'cost': item['cost'] * 10 + 100,
                'min': item['min'],
            })
            assert updated.status_code == 200, updated.text
        history_response = c.get('/api/orders/history', params={'from_ms': original['createdAt'] - 1, 'to_ms': original['createdAt'] + 86400000}, headers=h)
        assert history_response.status_code == 200, history_response.text
        history = history_response.json()
        # The history endpoint returns a list of order snapshots.
        saved = next(o for o in history if o['id'] == original['id'])
        assert saved['cost'] == original['cost']
        assert saved['items'] == original['items']
        finance_after = c.get('/api/reports/finance?days=1', headers=h).json()
        assert finance_after['cogs'] == finance_before['cogs']
        fresh = c.post('/api/orders', json=body, headers=h)
        assert fresh.status_code == 200, fresh.text
        assert fresh.json()['cost'] > original['cost']
        assert c.get('/api/reports/finance?days=1', headers=h).json()['cogs'] == original['cost'] + fresh.json()['cost']
