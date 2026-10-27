"""G5: device registry, offline conflicts, release rollout/rollback and client version gate."""
from uuid import uuid4

from fastapi.testclient import TestClient

from helpers import LATTE, new_company, staff_login
from test_api import app

KEY = "test-platform-key-not-a-secret"


def test_device_registration_binding_revoke_and_policy():
    with TestClient(app) as c:
        h, slug = new_company(c, "dev")
        kassir, _ = staff_login(c, h, slug, "kassir", "1357")
        second = c.post("/api/branches", json={"name": "B2"}, headers=h).json()["id"]
        assert c.post("/api/devices", headers=kassir, json={"name": "Kassa"}).status_code == 403
        dev = c.post("/api/devices", headers=h, json={"name": "Kassa 2", "branchId": second}).json()
        token = dev.pop("token")
        assert token.startswith("dev_") and token not in str(c.get("/api/devices", headers=h).json())
        bound = {**kassir, "X-Device-Token": token, "X-App-Version": "1.2.3"}
        assert c.get("/api/branches", headers=bound).json()["current"] == second
        seen = c.get("/api/devices", headers=h).json()[0]
        assert seen["lastSeenAt"] and seen["appVersion"] == "1.2.3"
        assert c.put("/api/devices/policy", headers=h, json={"requireDevice": True}).json()["requireDevice"]
        assert c.get("/api/sync", headers=kassir).status_code == 401
        assert c.get("/api/sync", headers=bound).status_code == 200
        other, _ = new_company(c, "dvx")
        assert c.get("/api/sync", headers={**other, "X-Device-Token": token}).status_code == 401
        assert c.post(f"/api/devices/{dev['id']}/revoke", headers=h).json()["revokedAt"]
        assert c.get("/api/sync", headers=bound).status_code == 401


def test_offline_sale_rules_and_conflict_queue():
    with TestClient(app) as c:
        h, _ = new_company(c, "off")
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        sale = {**LATTE, "payment": "naqd", "offline": True, "offlineCreatedAt": 1, "clientKey": uuid4().hex}
        assert c.post("/api/orders", headers=h, json={**sale, "payment": "karta"}).status_code == 422
        assert c.post("/api/orders", headers=h, json={**sale, "clientKey": None}).status_code == 422
        ok = c.post("/api/orders", headers=h, json=sale)
        assert ok.status_code == 200 and ok.json()["fiscalStatus"] == "nonfiscal"
        assert c.post("/api/orders", headers=h, json=sale).json()["id"] == ok.json()["id"]
        bad = {**sale, "clientKey": uuid4().hex, "expectedTotal": 1}
        first = c.post("/api/orders", headers=h, json=bad)
        assert first.status_code == 409 and first.json()["detail"]["code"] == "offline_conflict"
        assert c.post("/api/orders", headers=h, json=bad).json()["detail"]["conflictId"] == \
            first.json()["detail"]["conflictId"]
        conflicts = c.get("/api/offline/conflicts", headers=h).json()
        assert len(conflicts) == 1 and conflicts[0]["expectedTotal"] == 1
        cid = conflicts[0]["id"]
        assert c.post(f"/api/offline/conflicts/{cid}/resolve", headers=h).json()["status"] == "resolved"
        assert c.post(f"/api/offline/conflicts/{cid}/resolve", headers=h).status_code == 409
        assert c.get("/api/offline/conflicts", headers=h).json() == []


def test_release_rollout_rollback_and_min_version(monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", KEY)
    with TestClient(app) as c:
        h, _ = new_company(c, "upd")
        admin = {"X-Platform-Key": KEY}
        platform = "web"
        version = f"9.{uuid4().int % 1000}.0"
        body = {"platform": platform, "version": version, "rolloutPercent": 0, "minSupported": "1.0.0"}
        assert c.post("/api/platform/releases", json=body).status_code == 403
        assert c.post("/api/platform/releases", headers={"X-Platform-Key": "x"}, json=body).status_code == 403
        assert c.post("/api/platform/releases", headers=admin, json={**body, "version": "1.0"}).status_code == 422
        future = c.post("/api/platform/releases", headers=admin, json={
            **body, "version": f"{version[:-1]}5", "minBackend": "99.0.0", "rolloutPercent": 100})
        assert future.status_code == 201  # incompatible with this backend, never offered
        rel = c.post("/api/platform/releases", headers=admin, json=body)
        assert rel.status_code == 201
        assert c.post("/api/platform/releases", headers=admin, json=body).status_code == 409
        check = c.get(f"/api/updates/check?platform={platform}&version=1.0.0", headers=h).json()
        assert check["update"] is None or check["update"]["version"] != version  # 0 % rollout
        assert c.post(f"/api/platform/releases/{rel.json()['id']}/rollout", headers=admin,
                      json={"rolloutPercent": 100}).status_code == 200
        check = c.get(f"/api/updates/check?platform={platform}&version=1.0.0", headers=h).json()
        assert check["update"]["version"] == version and check["mandatory"] is False
        assert c.get(f"/api/updates/check?platform={platform}&version=0.9.0", headers=h).json()["mandatory"]
        assert c.post(f"/api/platform/releases/{rel.json()['id']}/rollback", headers=admin).json()["status"] == \
            "rolled_back"
        after = c.get(f"/api/updates/check?platform={platform}&version={version}", headers=h).json()
        assert after["update"] is None or after["rollback"] is True
        monkeypatch.setenv("MIN_CLIENT_VERSION", "2.0.0")
        assert c.get("/api/sync", headers={**h, "X-App-Version": "1.9.9"}).status_code == 426
        assert c.get("/api/sync", headers={**h, "X-App-Version": "2.0.0"}).status_code == 200
