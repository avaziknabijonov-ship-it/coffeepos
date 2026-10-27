"""A branch selection must not mutate or replay another branch's parked order."""
from uuid import uuid4

from fastapi.testclient import TestClient

from helpers import LATTE, at, new_company, staff_login
from test_api import app


def setup_draft(c):
    owner, _ = new_company(c, 'draftbranch')
    second = c.post('/api/branches', headers=owner, json={'name': 'Second'}).json()['id']
    body = {'clientKey': uuid4().hex, 'items': LATTE['items'], 'customer': 'Private draft'}
    draft = c.post('/api/drafts', headers=owner, json=body)
    assert draft.status_code == 201, draft.text
    return owner, at(owner, second), body, draft.json()


def test_draft_delete_does_not_cross_branch():
    with TestClient(app) as c:
        owner, other, _, draft = setup_draft(c)
        assert c.delete(f"/api/drafts/{draft['id']}?version=1", headers=other).status_code == 404
        assert [x['id'] for x in c.get('/api/drafts', headers=owner).json()] == [draft['id']]
        assert c.delete(f"/api/drafts/{draft['id']}?version=1", headers=owner).status_code == 204


def test_draft_idempotency_key_does_not_reveal_other_branch_content():
    with TestClient(app) as c:
        owner, other, body, draft = setup_draft(c)
        r = c.post('/api/drafts', headers=other, json=body)
        assert r.status_code == 409, r.text
        assert 'Private draft' not in r.text
        assert c.post('/api/drafts', headers=owner, json=body).json()['id'] == draft['id']


def test_draft_update_hides_other_branch_existence():
    with TestClient(app) as c:
        owner, other, body, draft = setup_draft(c)
        update = {'version': 1, 'items': body['items'], 'customer': 'Changed'}
        assert c.patch(f"/api/drafts/{draft['id']}", headers=other, json=update).status_code == 404
        assert c.get('/api/drafts', headers=owner).json()[0]['customer'] == 'Private draft'


def test_cashier_branch_header_requires_assignment_or_bound_device():
    with TestClient(app) as c:
        owner, slug = new_company(c, 'branchrbac')
        second = c.post('/api/branches', headers=owner, json={'name': 'Second'}).json()['id']
        cashier, _ = staff_login(c, owner, slug, 'kassir', '1357')
        default_id = c.get('/api/branches', headers=cashier).json()['current']
        assert c.get('/api/sync', headers=at(cashier, default_id)).status_code == 200
        assert c.get('/api/sync', headers=at(cashier, second)).status_code == 403
        device = c.post('/api/devices', headers=owner, json={'name': 'Branch POS', 'branchId': second}).json()
        bound = {**cashier, 'X-Device-Token': device['token']}
        assert c.get('/api/branches', headers=bound).json()['current'] == second
        assert c.get('/api/sync', headers=at(bound, default_id)).status_code == 403
        assert c.get('/api/sync', headers=at(owner, second)).status_code == 200
