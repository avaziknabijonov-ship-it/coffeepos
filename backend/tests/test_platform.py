import os
from fastapi.testclient import TestClient
from app.main import app

def test_platform_create_suspend_and_renew(monkeypatch):
    monkeypatch.setenv("SUPERADMIN_KEY", "A" * 48)
    with TestClient(app) as c:
        path = "/api/superadmin/companies"
        key = {"X-Superadmin-Key": "A" * 48}
        assert c.get(path).status_code == 401
        r = c.post(path, headers=key, json={"slug": "platform-test-12", "name": "Test Cafe",
            "owner_name": "Owner", "owner_pin": "6832", "plan": "monthly", "days": 30})
        assert r.status_code == 201, r.text
        before = r.json()["subscription"]["expiresAt"]
        url = path + "/platform-test-12/subscription"
        r = c.post(url, headers=key, json={"action": "renew", "plan": "yearly", "days": 365})
        assert r.status_code == 200 and r.json()["subscription"]["expiresAt"] > before
        assert c.post(url, headers=key, json={"action": "suspend"}).status_code == 200
        monkeypatch.setenv("ENFORCE_LICENSES", "1")
        login = c.post("/api/auth/login", json={"company": "platform-test-12", "pin": "6832"})
        assert login.status_code == 403
        assert c.post(url, headers=key, json={"action": "grant", "plan": "monthly", "days": 30}).status_code == 200
        assert c.post("/api/auth/login", json={"company": "platform-test-12", "pin": "6832"}).status_code == 200
