from fastapi.testclient import TestClient
from app.main import app
from test_api import login


def test_floor_layout_permissions_validation_and_concurrent_edits():
    with TestClient(app) as c:
        owner, cashier = login(c, '1111'), login(c, '2222')
        area = c.post('/api/areas', headers=owner, json={'name': 'Layout hall'}).json()
        table = c.post('/api/tables', headers=owner, json={'areaId': area['id'], 'name': 'VIP layout'}).json()
        path = f"/api/tables/{table['id']}/layout"
        body = {'x': 850, 'y': 100, 'width': 90, 'height': 400, 'shape': 'vip', 'version': 1}
        assert c.patch(path, headers=cashier, json=body).status_code == 403
        assert c.patch(path, headers=owner, json={**body, 'x': 950}).status_code == 422
        assert c.patch(path, headers=owner, json={**body, 'width': 300}).status_code == 422
        result = c.patch(path, headers=owner, json=body)
        assert result.status_code == 200, result.text
        assert result.json()['layoutVersion'] == 2
        assert c.patch(path, headers=owner, json=body).status_code == 409
        saved = next(x for x in c.get('/api/floor', headers=cashier).json()['tables'] if x['id'] == table['id'])
        assert saved['layout'] == {k: v for k, v in body.items() if k != 'version'}
        assert saved['layoutVersion'] == 2
        from app.db import SessionLocal
        from app.main import create_company
        import secrets
        slug = 'layout-' + secrets.token_hex(4)
        with SessionLocal() as db:
            create_company(db, slug, 'Other', 'Owner', '1234')
            db.commit()
        assert c.patch(path, headers=login(c, '1234', slug), json={**body, 'version': 2}).status_code == 404
