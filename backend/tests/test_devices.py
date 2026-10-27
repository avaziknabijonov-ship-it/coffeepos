import hashlib
import jwt
from sqlalchemy import select
from fastapi.testclient import TestClient
from app.db import AuditEvent, Device, SessionLocal, now_ms
from app.security import secret_key
from test_api import app
from test_refunds_api import company


def setup_company(c):
    owner = company(c)
    slug = c.get('/api/me', headers=owner).json()['company']['slug']
    for role, pin in [('kassir', '2222'), ('barista', '3333'), ('admin', '4444')]:
        r = c.post('/api/staff', headers=owner, json={'name': role, 'role': role, 'pin': pin})
        assert r.status_code == 200, r.text
    return owner, slug


def sign_in(c, slug, pin='2222', secret=None):
    body = {'company': slug, 'pin': pin}
    if secret is not None:
        body['deviceSecret'] = secret
    return c.post('/api/auth/login', json=body)


def auth_header(result):
    return {'Authorization': 'Bearer ' + result.json()['token']}


def test_device_enrollment_role_tenant_privacy_and_revocation():
    with TestClient(app) as c:
        owner, slug = setup_company(c)
        other = company(c)
        cashier = auth_header(sign_in(c, slug))
        assert c.get('/api/devices').status_code == 401
        assert c.get('/api/devices', headers=cashier).status_code == 403
        assert c.post('/api/devices', headers=cashier, json={'name': 'Fake'}).status_code == 403
        assert c.post('/api/devices', headers=owner, json={'name': '  '}).status_code == 422
        enrolled = c.post('/api/devices', headers=owner, json={'name': 'Front tablet'})
        assert enrolled.status_code == 201, enrolled.text
        result = enrolled.json()
        did, secret = result['device']['id'], result['deviceSecret']
        bound_owner = auth_header(enrolled)
        listing = c.get('/api/devices', headers=bound_owner).json()
        assert listing['currentDeviceId'] == did
        assert listing['items'][0]['name'] == 'Front tablet'
        assert 'secret' not in str(listing).lower() and secret not in str(listing)
        assert c.get('/api/devices', headers=other).json()['items'] == []
        assert c.post(f'/api/devices/{did}/revoke', headers=other).status_code == 404
        assert c.post(f'/api/devices/{did}/revoke', headers=cashier).status_code == 403
        active_login = sign_in(c, slug, secret=secret)
        assert active_login.status_code == 200, active_login.text
        bound_cashier = auth_header(active_login)
        assert c.get('/api/menu', headers=bound_cashier).status_code == 200
        with SessionLocal() as db:
            row = db.get(Device, did)
            assert row.secret_hash == hashlib.sha256(secret.encode()).hexdigest()
            row.last_seen_at = 0
            db.commit()
        assert c.get('/api/me', headers=bound_cashier).status_code == 200
        with SessionLocal() as db:
            assert db.get(Device, did).last_seen_at > now_ms() - 60_000
        assert c.post(f'/api/devices/{did}/revoke', headers=owner).status_code == 200
        assert c.post(f'/api/devices/{did}/revoke', headers=owner).status_code == 200
        assert c.get('/api/me', headers=bound_owner).status_code == 401
        assert c.get('/api/menu', headers=bound_cashier).status_code == 401
        assert sign_in(c, slug, secret=secret).status_code == 403
        # Optional mode retains compatibility for old, unbound clients.
        assert c.get('/api/me', headers=cashier).status_code == 200
        with SessionLocal() as db:
            events = list(db.scalars(select(AuditEvent).where(
                AuditEvent.company_id == db.get(Device, did).company_id,
                AuditEvent.action == 'device.revoke', AuditEvent.entity_id == did)))
            assert len(events) == 1
            assert secret not in str(events[0].after)


def test_required_policy_blocks_legacy_sessions_and_allows_manager_recovery():
    with TestClient(app) as c:
        owner, slug = setup_company(c)
        cashier = auth_header(sign_in(c, slug))
        barista = auth_header(sign_in(c, slug, '3333'))
        admin = auth_header(sign_in(c, slug, '4444'))
        body = {'required': True}
        assert c.put('/api/devices/policy', headers=cashier, json=body).status_code == 403
        assert c.put('/api/devices/policy', headers=admin, json=body).status_code == 403
        assert c.put('/api/devices/policy', headers=owner, json=body).json() == body
        for headers, pin in ((cashier, '2222'), (barista, '3333')):
            assert c.get('/api/me', headers=headers).status_code == 401
            assert sign_in(c, slug, pin).status_code == 403
        assert c.get('/api/me', headers=owner).status_code == 200
        assert sign_in(c, slug, '1111').status_code == 200
        assert sign_in(c, slug, '4444').status_code == 200
        result = c.post('/api/devices', headers=owner, json={'name': 'Approved kiosk'}).json()
        bound = auth_header(sign_in(c, slug, secret=result['deviceSecret']))
        assert c.get('/api/me', headers=bound).status_code == 200
        assert c.post(f"/api/devices/{result['device']['id']}/revoke", headers=owner).status_code == 200
        assert c.get('/api/me', headers=bound).status_code == 401
        assert sign_in(c, slug).status_code == 403  # Clearing local storage cannot bypass policy.
        assert c.put('/api/devices/policy', headers=owner, json={'required': False}).status_code == 200
        assert c.get('/api/me', headers=cashier).status_code == 200


def test_device_claim_and_credential_cannot_cross_companies():
    with TestClient(app) as c:
        owner, slug = setup_company(c)
        other, other_slug = setup_company(c)
        grant = c.post('/api/devices', headers=owner, json={'name': 'First company'}).json()
        assert sign_in(c, other_slug, '1111', grant['deviceSecret']).status_code == 403
        token = other['Authorization'].removeprefix('Bearer ')
        with SessionLocal() as db:
            key = secret_key(db)
            claims = jwt.decode(token, key, algorithms=['HS256'])
        for did in (grant['device']['id'], 999999999, 'not-an-id', True):
            forged = jwt.encode({**claims, 'did': did}, key, algorithm='HS256')
            assert c.get('/api/me', headers={'Authorization': 'Bearer ' + forged}).status_code == 401
        assert sign_in(c, slug, secret='x' * 43).status_code == 403
        assert sign_in(c, slug, secret='bad').status_code == 422


def test_device_tables_migrate_existing_database_without_rewriting_staff(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker
    from app import main
    from app.db import Base, Company, DevicePolicy, Staff
    from app.security import hash_pin
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy-device.db'))
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables
                                           if table.name not in {'devices', 'device_policies'}])
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        tenant = Company(slug='legacy-device', name='Existing Coffee')
        db.add(tenant)
        db.flush()
        db.add(Staff(company_id=tenant.id, name='Original Owner', role='owner', pin_hash=hash_pin('1111')))
        db.commit()
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setenv('SEED_DEMO', '0')
    main.init_db()
    main.init_db()
    assert {'devices', 'device_policies'} <= set(inspect(engine).get_table_names())
    with sessions() as db:
        assert db.scalar(select(Company.name)) == 'Existing Coffee'
        assert db.scalar(select(Staff.name)) == 'Original Owner'
        assert list(db.scalars(select(Device))) == []
        assert list(db.scalars(select(DevicePolicy))) == []  # Legacy clients remain allowed.
    engine.dispose()
