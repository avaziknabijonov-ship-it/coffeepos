"""Privacy deletion, tenant isolation and old-token replay regression tests."""
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db import Base, Company, SessionLocal, engine
from app.main import app


def create(client, slug, pin='7654'):
    r = client.post('/api/auth/register', json={'companyName': slug, 'slug': slug, 'ownerName': 'QA Owner', 'ownerPin': pin})
    assert r.status_code == 200, r.text
    return {'Authorization': 'Bearer ' + r.json()['token']}


def test_delete_requires_owner_pin_confirmation_and_preserves_other_tenants(monkeypatch):
    with TestClient(app) as c:
        owner = create(c, 'privacy-delete-qa')
        other = create(c, 'privacy-keep-qa')
        staff = c.post('/api/staff', headers=owner, json={'name': 'QA Staff', 'pin': '8765', 'role': 'kassir'})
        assert staff.status_code == 200
        token = c.post('/api/auth/login', json={'company': 'privacy-delete-qa', 'pin': '8765'}).json()['token']
        assert c.delete('/api/account').status_code == 401
        body = {'company': 'privacy-delete-qa', 'pin': '7654'}
        assert c.request('DELETE', '/api/account', headers={'Authorization': 'Bearer '+token}, json=body).status_code == 403
        assert c.request('DELETE', '/api/account', headers=owner, json={**body, 'pin': '1112'}).status_code == 403
        assert c.request('DELETE', '/api/account', headers=owner, json={**body, 'company': 'privacy-keep-qa'}).status_code == 403
        assert c.get('/api/me', headers=owner).status_code == 200
        with SessionLocal() as db:
            cid = db.scalar(select(Company).where(Company.slug == body['company'])).id
        assert c.post('/api/shifts/open', headers=owner, json={'openingCash': 50000}).status_code == 200
        order = c.post('/api/orders', headers=owner, json={'items': [{'productId': 'latte', 'size': 'M', 'qty': 1}], 'payment': 'qarz', 'customer': 'QA Customer'})
        assert order.status_code == 200, order.text
        debt = c.get('/api/debts', headers=owner).json()[0]['id']
        assert c.post(f'/api/debts/{debt}/payments', headers=owner, json={'amount': 100, 'method': 'naqd'}).status_code == 200
        assert c.post('/api/expenses', headers=owner, json={'amount': 10, 'category': 'QA', 'method': 'naqd'}).status_code == 200
        # Enable real SQLite FK enforcement during the operation.
        if engine.dialect.name == 'sqlite':
            with engine.connect() as connection:
                connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        monkeypatch.setenv('LICENSE_ENFORCEMENT', '1')
        with SessionLocal() as db:
            from app.db import Subscription
            sub = db.scalar(select(Subscription).where(Subscription.company_id == cid))
            sub.status = 'suspended'; db.commit()
        assert c.request('DELETE', '/api/account', headers=owner, json=body).status_code == 200
        assert c.get('/api/me', headers=owner).status_code == 401
        assert c.get('/api/me', headers=other).status_code == 200
        with SessionLocal() as db:
            assert db.get(Company, cid) is None
            for table in Base.metadata.sorted_tables:
                if 'company_id' in table.c:
                    assert db.execute(select(table).where(table.c.company_id == cid)).first() is None


def test_pin_change_revokes_old_tokens():
    with TestClient(app) as c:
        owner = create(c, 'privacy-token-qa')
        with SessionLocal() as db:
            from app.db import Staff
            from app.security import hash_pin
            company = db.scalar(select(Company).where(Company.slug == 'privacy-token-qa'))
            staff = db.scalar(select(Staff).where(Staff.company_id == company.id))
            staff.pin_hash = hash_pin('9087'); db.commit()
        assert c.get('/api/me', headers=owner).status_code == 401
        r = c.post('/api/auth/login', json={'company': 'privacy-token-qa', 'pin': '9087'})
        assert r.status_code == 200
        assert c.get('/api/me', headers={'Authorization': 'Bearer '+r.json()['token']}).status_code == 200


def test_deleted_tenant_token_cannot_access_recreated_account():
    with TestClient(app) as c:
        old = create(c, 'privacy-recycled-qa')
        assert c.request('DELETE', '/api/account', headers=old, json={'company': 'privacy-recycled-qa', 'pin': '7654'}).status_code == 200
        fresh = create(c, 'privacy-recycled-qa')
        assert c.get('/api/me', headers=old).status_code == 401
        assert c.get('/api/me', headers=fresh).status_code == 200
