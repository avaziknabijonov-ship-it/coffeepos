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


def test_receipt_revocation_survives_new_session_and_is_tenant_scoped():
    from sqlalchemy import select
    from app.db import AuditEvent, ReceiptLink
    with TestClient(app) as c:
        h, other = company(c), company(c)
        c.post('/api/shifts/open', headers=h, json={'openingCash': 0})
        order = c.post('/api/orders', headers=h, json={
            'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}], 'payment': 'karta'
        }).json()
        url = f"/api/orders/{order['id']}/receipt-link"
        revoke = f"/api/orders/{order['id']}/receipt-links"
        first = c.post(url, headers=h).json()
        second = c.post(url, headers=h).json()
        assert first['linkId'] != second['linkId']
        assert c.delete(revoke).status_code == 401
        assert c.delete(revoke, headers=other).status_code == 404
        assert c.delete(revoke, headers=login(c, '2222')).status_code == 403
        assert c.get(first['path']).status_code == 200
        assert c.delete(revoke, headers=h).json() == {'revoked': 2}
        assert c.delete(revoke, headers=h).json() == {'revoked': 0}
        for link in (first, second):
            denied = c.get(link['path'])
            assert denied.status_code == 404
        with SessionLocal() as db:
            grant = db.get(ReceiptLink, first['linkId'])
            assert grant.revoked_at is not None
            assert first['path'].rsplit('/', 1)[1] not in repr(grant.__dict__)
            events = list(db.scalars(select(AuditEvent).where(
                AuditEvent.company_id == grant.company_id, AuditEvent.entity_id == int(order['id']),
                AuditEvent.action == 'receipt.revoke')))
            assert len(events) == 1
            assert 'jti' not in str(events[0].after)
        fresh = c.post(url, headers=h).json()
        assert c.get(fresh['path']).status_code == 200
        assert c.get(first['path']).status_code == 404


def test_unregistered_or_database_expired_receipt_grant_is_rejected():
    from app.db import ReceiptLink, now_ms
    with TestClient(app) as c:
        h = company(c)
        c.post('/api/shifts/open', headers=h, json={'openingCash': 0})
        order = c.post('/api/orders', headers=h, json={
            'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}], 'payment': 'karta'
        }).json()
        link = c.post(f"/api/orders/{order['id']}/receipt-link", headers=h).json()
        with SessionLocal() as db:
            key = secret_key(db)
            claims = jwt.decode(link['path'].rsplit('/', 1)[1], key,
                                algorithms=['HS256'], audience='coffeepos-public-receipt')
            forged = jwt.encode({**claims, 'jti': 'unregistered'}, key, algorithm='HS256')
            malformed = jwt.encode({**claims, 'jti': 123}, key, algorithm='HS256')
            grant = db.get(ReceiptLink, link['linkId'])
            grant.expires_at = now_ms() - 1
            db.commit()
        assert c.get(link['path']).status_code == 404
        assert c.get('/api/public/receipts/' + forged).status_code == 404
        assert c.get('/api/public/receipts/' + malformed).status_code == 404
