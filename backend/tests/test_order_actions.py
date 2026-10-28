import secrets
from fastapi.testclient import TestClient
from app.main import app
from test_api import login


def test_split_move_note_assignment_and_checkout():
    with TestClient(app) as c:
        owner, cashier = login(c, '1111'), login(c, '2222')
        area = c.post('/api/areas', headers=owner, json={'name': 'Action ' + secrets.token_hex(3)}).json()
        tables = [c.post('/api/tables', headers=owner, json={'areaId': area['id'], 'name': str(n)}).json() for n in [1, 2]]
        items = [{'productId': 'espresso', 'size': '-', 'qty': 1, 'guest': n} for n in [1, 2]]
        draft = c.post('/api/drafts', headers=owner, json={'clientKey': secrets.token_hex(16), 'items': items, 'tableId': tables[0]['id'], 'service': 'dine_in', 'note': 'Less sugar', 'guestCount': 4}).json()
        path = f"/api/drafts/{draft['id']}"
        staff = c.get('/api/staff', headers=owner).json()[0]
        assert c.post(path + '/assign', headers=cashier, json={'version': 1, 'staffId': staff['id']}).status_code == 403
        assert c.post(path + '/assign', headers=owner, json={'version': 1, 'staffId': staff['id']}).status_code == 200
        assert c.post(path + '/split', headers=owner, json={'version': 1, 'guest': 2}).status_code == 409
        split = c.post(path + '/split', headers=owner, json={'version': 2, 'guest': 2})
        assert split.status_code == 201, split.text
        drafts = {d['id']: d for d in c.get('/api/drafts', headers=owner).json()}
        a, b = drafts[draft['id']], drafts[split.json()['id']]
        assert a['note'] == b['note'] == 'Less sugar'
        assert a['waiter'] == b['waiter'] == staff['name']
        assert a['guestCount'] == b['guestCount'] == 4
        assert [i['guest'] for i in a['items']] == [1]
        assert [i['guest'] for i in b['items']] == [2]
        assert c.post(path + '/move', headers=owner, json={'version': a['version'], 'tableId': tables[1]['id'], 'service': 'dine_in'}).status_code == 200
        c.post('/api/shifts/open', headers=owner, json={'openingCash': 0})
        order = c.post('/api/orders', headers=owner, json={'draftId': b['id'], 'draftVersion': b['version'], 'items': b['items'], 'note': b['note'], 'guestCount': 4, 'payment': 'karta'})
        assert order.status_code == 200, order.text
        assert order.json()['note'] == 'Less sugar'
        assert order.json()['waiter'] == staff['name']
        assert order.json()['total'] == 15000
        floor = c.get('/api/floor', headers=owner).json()
        assert not next(t for t in floor['tables'] if t['id'] == tables[0]['id'])['occupied']
        assert c.delete(path + '?version=' + str(a['version'] + 1), headers=owner).status_code == 204
        assert not next(t for t in c.get('/api/floor', headers=owner).json()['tables'] if t['id'] == tables[1]['id'])['occupied']
