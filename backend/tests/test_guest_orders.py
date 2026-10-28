from fastapi.testclient import TestClient
from app.main import app
from test_api import login
import secrets


def test_guest_items_survive_draft_and_atomic_checkout():
    with TestClient(app) as c:
        h = login(c, '1111')
        c.post('/api/shifts/open', headers=h, json={'openingCash': 0})
        items = [{'productId': 'espresso', 'size': '-', 'modIds': [], 'qty': 1, 'guest': guest} for guest in [1, 2]]
        r = c.post('/api/drafts', headers=h, json={'clientKey': secrets.token_hex(16), 'items': items})
        assert r.status_code == 201, r.text
        draft = r.json()
        assert [i['guest'] for i in draft['items']] == [1, 2]
        result = c.post('/api/orders', headers=h, json={'draftId': draft['id'], 'draftVersion': draft['version'], 'items': items, 'payment': 'karta'})
        assert result.status_code == 200, result.text
        order = result.json()
        assert len(order['items']) == 2
        assert [i.get('guest', 1) for i in order['items']] == [1, 2]
        assert len({i['key'] for i in order['items']}) == 2
        assert order['total'] == 30000
        assert not any(d['id'] == draft['id'] for d in c.get('/api/drafts', headers=h).json())
        assert c.post('/api/drafts', headers=h, json={'clientKey': secrets.token_hex(16), 'items': [{**items[0], 'guest': 51}]}).status_code == 422
