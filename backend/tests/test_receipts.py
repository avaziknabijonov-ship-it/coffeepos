import time
import jwt
from fastapi.testclient import TestClient
from app.db import Order, SessionLocal
from app.security import secret_key
from test_api import app, login
from test_refunds_api import company


def test_receipt_links_privacy_expiration_and_token_scope():
    with TestClient(app) as c:
        h, other = company(c), company(c)
        assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
        response = c.post('/api/orders', headers=h, json={
            'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}],
            'payment': 'karta', 'customer': 'Private customer 998901234567',
        })
        assert response.status_code == 200, response.text
        order = response.json()
        url = f"/api/orders/{order['id']}/receipt-link"
        assert c.post(url).status_code == 401
        assert c.post(url, headers=other).status_code == 404
        assert c.post(url, headers=login(c, '2222')).status_code == 403
        result = c.post(url, headers=h)
        assert result.status_code == 200, result.text
        link = result.json()
        assert link['expiresIn'] == 900 and link['fiscal'] is False
        path = link['path']
        token = path.rsplit('/', 1)[1]
        with SessionLocal() as db:
            key = secret_key(db)
            claims = jwt.decode(token, key, algorithms=['HS256'], audience='coffeepos-public-receipt')
            stored = db.get(Order, int(order['id']))
            stored.items = [{**item, 'name': '<script>alert(1)</script>'} for item in stored.items]
            db.commit()
        receipt = c.get(path)
        assert receipt.status_code == 200, receipt.text
        assert 'FISKAL CHEK EMAS' in receipt.text
        assert 'Private customer' not in receipt.text and '998901234567' not in receipt.text
        assert '<script>' not in receipt.text and '&lt;script&gt;' in receipt.text
        assert 'unitCost' not in receipt.text and 'consumption' not in receipt.text
        assert receipt.headers['cache-control'] == 'no-store, private'
        assert receipt.headers['referrer-policy'] == 'no-referrer'
        assert "frame-ancestors 'none'" in receipt.headers['content-security-policy']
        assert 'НЕ ФИСКАЛЬНЫЙ ЧЕК' in c.get(path + '?lang=ru').text
        assert c.get('/api/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401
        session_token = h['Authorization'].removeprefix('Bearer ')
        assert c.get('/api/public/receipts/' + session_token).status_code == 404
        for changed in ({'exp': int(time.time()) - 1}, {'aud': 'wrong-purpose'},
                        {'oid': 999999999}, {'cid': 999999999}, {'purpose': 'login'}):
            invalid = jwt.encode({**claims, **changed}, key, algorithm='HS256')
            assert c.get('/api/public/receipts/' + invalid).status_code == 404
        assert c.get('/api/public/receipts/not-a-valid-token').status_code == 404
