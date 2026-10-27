import secrets
from fastapi.testclient import TestClient
from app.main import app
from test_api import login


def test_optional_hookah_license_lifecycle_and_tenant_isolation(monkeypatch):
    monkeypatch.setenv('SUPERADMIN_KEY', 'L' * 48)
    monkeypatch.setenv('ENFORCE_LICENSES', '0')
    platform = {'X-Superadmin-Key': 'L' * 48}
    with TestClient(app) as c:
        slug = 'hookah-' + secrets.token_hex(4)
        other = 'plain-' + secrets.token_hex(4)
        body = {'slug': slug, 'name': 'Hookah venue', 'owner_name': 'Owner', 'owner_pin': '4433', 'modules': ['hookah']}
        response = c.post('/api/superadmin/companies', headers=platform, json=body)
        assert response.status_code == 201, response.text
        assert response.json()['subscription']['modules'] == ['hookah']
        assert c.post('/api/superadmin/companies', headers=platform, json={**body, 'slug': other, 'modules': []}).status_code == 201
        user, plain = login(c, '4433', slug), login(c, '4433', other)
        assert c.get('/api/me', headers=user).json()['company']['modules'] == ['hookah']
        menu = c.get('/api/menu', headers=user).json()
        assert len(menu['categories']) == 4 and menu['products'] == [] and menu['ingredients'] == []
        assert c.get('/api/modules/hookah', headers=user).status_code == 200
        assert c.get('/api/modules/hookah', headers=plain).status_code == 403
        assert c.get('/api/modules/hookah').status_code == 401
        path = '/api/superadmin/companies/' + slug + '/subscription'
        assert c.post(path, headers=user, json={'action': 'grant', 'modules': ['hookah']}).status_code == 401
        assert c.post(path, headers=platform, json={'action': 'renew'}).json()['subscription']['modules'] == ['hookah']
        assert len(c.get('/api/menu', headers=user).json()['categories']) == 4
        assert c.post(path, headers=platform, json={'action': 'renew', 'modules': ['unrecognized']}).status_code == 422
        assert c.post(path, headers=platform, json={'action': 'renew', 'modules': []}).status_code == 200
        assert c.get('/api/modules/hookah', headers=user).status_code == 403
        assert c.get('/api/me', headers=user).json()['company']['modules'] == []
        assert c.post(path, headers=platform, json={'action': 'grant', 'modules': ['hookah']}).status_code == 200
        assert c.post(path, headers=platform, json={'action': 'suspend'}).status_code == 200
        assert c.get('/api/modules/hookah', headers=user).status_code == 403
        assert c.post(path, headers=platform, json={'action': 'grant', 'modules': ['hookah']}).status_code == 200
        from app.db import SessionLocal, Company, Subscription, now_ms
        from sqlalchemy import select
        with SessionLocal() as db:
            company = db.scalar(select(Company).where(Company.slug == slug))
            db.get(Subscription, company.id).expires_at = now_ms() - 1
            db.commit()
        assert c.get('/api/modules/hookah', headers=user).status_code == 403
        assert c.get('/api/me', headers=user).json()['company']['modules'] == []
