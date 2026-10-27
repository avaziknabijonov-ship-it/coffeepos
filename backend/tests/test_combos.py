from fastapi.testclient import TestClient
from test_api import app, login
from test_refunds_api import company


def test_combo_deducts_once_and_cancel_uses_historical_ledger():
    with TestClient(app) as c:
        h, other = company(c), company(c)
        assert c.post('/api/purchases', headers=h, json={
            'number': 'COMBO-IN', 'supplier': 'Test', 'received_at': 1780000000000,
            'payment_status': 'paid', 'lines': [
                {'ing': 'beans', 'qty': 1000, 'unit_price': 100},
                {'ing': 'milk', 'qty': 1000, 'unit_price': 20}],
        }).status_code == 200
        menu = c.get('/api/menu', headers=h).json()
        category = menu['products'][0]['cat']
        body = {'name': 'Two lattes and espresso', 'cat': category, 'price': 40000,
                'components': [{'productId': 'latte', 'size': 'M', 'qty': 2},
                               {'productId': 'espresso', 'size': '-', 'qty': 1}]}
        created = c.post('/api/combos', headers=h, json=body)
        assert created.status_code == 201, created.text
        combo = created.json()
        recipe = {r['ing']: r['qty'] for r in combo['sizes'][0]['recipe']}
        assert recipe['beans'] == 45 and recipe['milk'] == 480
        assert c.put('/api/combos/' + combo['id'], headers=other, json=body).status_code == 404
        assert c.get('/api/combos', headers=other).json() == []
        assert c.post('/api/combos', headers=login(c, '2222'), json=body).status_code == 403
        nested = {**body, 'components': [{'productId': combo['id'], 'size': '-', 'qty': 1}, body['components'][1]]}
        assert c.post('/api/combos', headers=h, json=nested).status_code == 409
        assert c.post('/api/combos', headers=h, json={**body, 'components': body['components'][:1] * 2}).status_code == 422
        assert c.delete('/api/products/latte', headers=h).status_code == 409
        assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
        before = c.get('/api/sync', headers=h).json()['stock']
        sale = c.post('/api/orders', headers=h, json={
            'items': [{'productId': combo['id'], 'size': '-', 'qty': 2}], 'payment': 'karta',
        })
        assert sale.status_code == 200, sale.text
        order = sale.json()
        assert order['total'] == 80000
        assert len(order['items'][0]['components']) == 2
        assert order['items'][0]['components'][0]['qty'] == 2
        stock = c.get('/api/sync', headers=h).json()['stock']
        assert stock['beans'] == before['beans'] - 90
        assert stock['milk'] == before['milk'] - 960
        assert c.put('/api/combos/' + combo['id'], headers=h, json={**body, 'price': 50000,
            'components': [{**body['components'][0], 'qty': 1}, body['components'][1]]}).status_code == 200
        # Return original consumption, not the new combo's recipe.
        assert c.post(f"/api/orders/{order['id']}/cancel", headers=h, json={'reason': 'Customer cancelled'}).status_code == 200
        assert c.get('/api/sync', headers=h).json()['stock'] == before
        assert c.post(f"/api/orders/{order['id']}/cancel", headers=h, json={'reason': 'Retry cancelled'}).status_code == 409
        assert c.get('/api/sync', headers=h).json()['stock'] == before
        assert c.patch('/api/products/latte/active', headers=h, json={'active': False}).status_code == 200
        listed = next(p for p in c.get('/api/menu', headers=h).json()['products'] if p['id'] == combo['id'])
        assert listed['active'] is False
        assert c.post('/api/orders', headers=h, json={
            'items': [{'productId': combo['id'], 'size': '-', 'qty': 1}], 'payment': 'karta',
        }).status_code == 400
