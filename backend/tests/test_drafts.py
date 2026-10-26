"""Parked-order API contract: idempotency, isolation, concurrency, no sale side effects."""
from uuid import uuid4
from fastapi.testclient import TestClient

from test_api import app, login


def test_parked_order_lifecycle():
    with TestClient(app) as client:
        owner = login(client, "1111")
        barista = login(client, "3333")
        key = "draft_" + uuid4().hex
        body = {"clientKey": key, "items": [
            {"productId": "latte", "size": "M", "modIds": [], "qty": 1}
        ], "customer": "Parked Customer"}
        before = client.get("/api/reports/daily", headers=owner).json()
        response = client.post("/api/drafts", json=body, headers=owner)
        assert response.status_code == 201, response.text
        draft = response.json()
        assert draft["version"] == 1
        assert client.post("/api/drafts", json=body, headers=owner).json()["id"] == draft["id"]
        assert client.post("/api/drafts", json={**body, "customer": "Different"}, headers=owner).status_code == 409
        assert client.get("/api/drafts", headers=barista).status_code == 403
        assert any(d["id"] == draft["id"] for d in client.get("/api/drafts", headers=owner).json())
        assert client.get("/api/reports/daily", headers=owner).json() == before

        changed = client.patch(f"/api/drafts/{draft['id']}", json={
            "version": 1, "items": body["items"], "customer": "Updated"
        }, headers=owner)
        assert changed.status_code == 200, changed.text
        assert changed.json()["version"] == 2
        assert client.patch(f"/api/drafts/{draft['id']}", json={
            "version": 1, "items": body["items"], "customer": "Stale"
        }, headers=owner).status_code == 409
        assert client.delete(f"/api/drafts/{draft['id']}?version=1", headers=owner).status_code == 409
        assert client.delete(f"/api/drafts/{draft['id']}?version=2", headers=owner).status_code == 204
        assert client.delete(f"/api/drafts/{draft['id']}?version=2", headers=owner).status_code == 404


def test_parked_order_tenant_isolation():
    with TestClient(app) as client:
        owner = login(client, "1111")
        slug = "drafts-" + uuid4().hex[:12]
        created = client.post("/api/auth/register", json={
            "companyName": "Other Coffee", "slug": slug,
            "ownerName": "Other", "ownerPin": "5544",
        })
        assert created.status_code == 200, created.text
        other = {"Authorization": f"Bearer {created.json()['token']}"}
        body = {"clientKey": "draft_" + uuid4().hex,
                "items": [{"productId": "latte", "size": "M", "qty": 1}],
                "customer": "Private"}
        response = client.post("/api/drafts", json=body, headers=owner)
        assert response.status_code == 201, response.text
        draft_id = response.json()["id"]
        assert all(d["id"] != draft_id for d in client.get("/api/drafts", headers=other).json())
        assert client.patch(f"/api/drafts/{draft_id}", json={
            "version": 1, "items": body["items"], "customer": "Unauthorized"
        }, headers=other).status_code == 404
        assert client.delete(f"/api/drafts/{draft_id}?version=1", headers=other).status_code == 404
        assert client.delete(f"/api/drafts/{draft_id}?version=1", headers=owner).status_code == 204
