import pytest
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from fastapi.testclient import TestClient
from app.audit import safe_snapshot
from test_api import app, login
from test_refunds_api import company
from app.db import SessionLocal


def test_audit_transaction_replay_privacy_and_pagination():
    with TestClient(app) as c:
        h, other = company(c), company(c)
        assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
        order = c.post('/api/orders', headers=h, json={
            'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}], 'payment': 'karta',
        }).json()
        body = {'clientKey': uuid4().hex, 'amount': 1000, 'method': 'karta',
                'reason': 'Private customer phone 998901234567', 'externalConfirmed': True}
        url = f"/api/orders/{order['id']}/refunds"
        assert c.post(url, headers=h, json=body).status_code == 201
        assert c.post(url, headers=h, json=body).status_code == 201
        assert c.post(url, headers=h, json={**body, 'clientKey': uuid4().hex, 'amount': 99999999}).status_code == 422
        page = c.get('/api/audit', headers=h).json()
        assert len(page['items']) == 1  # Retry and rejected operation do not add events.
        event = page['items'][0]
        assert event['action'] == 'order.refund'
        assert event['after'] == {'orderId': int(order['id']), 'amount': 1000, 'method': 'karta'}
        assert '998901234567' not in str(page)
        assert event['actorId'] > 0 and event['actor'] == 'Owner'
        assert c.get('/api/audit', headers=other).json()['items'] == []
        assert c.get('/api/audit').status_code == 401
        assert c.get('/api/audit', headers=login(c, '2222')).status_code == 403
        assert c.get('/api/audit?limit=101', headers=h).status_code == 422
        assert c.get('/api/audit?action=order.cancel', headers=h).json()['items'] == []
        assert c.get(f"/api/audit?before_id={event['id']}", headers=h).json()['items'] == []
        # A second, separate refund creates another immutable record.
        assert c.post(url, headers=h, json={**body, 'clientKey': uuid4().hex}).status_code == 201
        page = c.get('/api/audit?limit=1', headers=h).json()
        assert page['nextCursor'] is not None
        older = c.get(f"/api/audit?limit=1&before_id={page['nextCursor']}", headers=h).json()
        assert older['items'][0]['id'] == event['id']
        for sql in ('UPDATE audit_events SET action = :action WHERE id = :id',
                    'DELETE FROM audit_events WHERE id = :id'):
            with SessionLocal() as db:
                with pytest.raises(DBAPIError):
                    db.execute(text(sql), {'action': 'tampered', 'id': event['id']})
                    db.commit()
                db.rollback()


def test_sensitive_fields_are_not_saved_in_snapshots():
    assert safe_snapshot({'password': 'secret', 'lines': [{'ingredient': 'beans', 'token': 'secret'}],
                          'amount': 100, 'customer': {'phone': '99890'}}) == {
        'lines': [{'ingredient': 'beans'}], 'amount': 100}


def test_cancel_and_inventory_audit_and_failed_inventory_rollback():
    with TestClient(app) as c:
        h = company(c)
        assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
        order = c.post('/api/orders', headers=h, json={
            'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}], 'payment': 'karta',
        }).json()
        assert c.post(f"/api/orders/{order['id']}/cancel", headers=h,
                      json={'reason': 'Customer request'}).status_code == 200
        failed = c.post('/api/inventories', headers=h, json={
            'lines': [{'ing': 'beans', 'counted': 10}, {'ing': 'missing', 'counted': 0}],
        })
        assert failed.status_code == 404
        assert c.get('/api/audit?action=inventory.count', headers=h).json()['items'] == []
        assert c.post('/api/inventories', headers=h, json={
            'lines': [{'ing': 'beans', 'counted': 10}],
        }).status_code == 200
        records = c.get('/api/audit', headers=h).json()['items']
        assert {r['action'] for r in records} == {'order.cancel', 'inventory.count'}
        cancel = next(r for r in records if r['action'] == 'order.cancel')
        assert cancel['before'] == {'status': 'new'}
        assert cancel['after']['status'] == 'cancelled'
        inventory = next(r for r in records if r['action'] == 'inventory.count')
        assert inventory['after']['lines'][0]['counted'] == 10
