"""Isolated tests for per-admin MFA, permission boundaries and attributable license audit."""
import base64
import hashlib
import hmac
import struct
import time

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, PlatformAdmin, PlatformAudit, LicenseAudit
from app.main import app
from app.platform import get_db as platform_db


def code_for(secret: str) -> str:
    binary = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(binary, struct.pack(">Q", int(time.time() // 30)), "sha1").digest()
    offset = digest[-1] & 15
    return f"{(struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff) % 1000000:06d}"


def test_individual_admin_mfa_roles_history_and_revocation(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    bootstrap_key = "test-bootstrap-" + "K" * 40
    bootstrap_secret = base64.b32encode(b"bootstrap-secret-for-test-2026").decode().rstrip("=")
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", bootstrap_key)
    monkeypatch.setenv("PLATFORM_REQUIRE_MFA", "1")
    monkeypatch.setenv("PLATFORM_ADMIN_TOTP_SECRET", bootstrap_secret)
    monkeypatch.setenv("PLATFORM_REQUIRE_ADMIN_ACCOUNTS", "1")
    monkeypatch.setenv("PLATFORM_MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    app.dependency_overrides[platform_db] = override

    def enroll(client, username, token, password):
        start = client.post("/api/platform/enroll/start", json={
            "username": username, "enrollmentToken": token,
        })
        assert start.status_code == 200, start.text
        secret = start.json()["totpSecret"]
        with factory() as db:
            admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.username == username))
            assert secret not in admin.totp_encrypted
            assert admin.password_hash is None
        finish = client.post("/api/platform/enroll/complete", json={
            "username": username, "enrollmentToken": token,
            "password": password, "code": code_for(secret),
        })
        assert finish.status_code == 200, finish.text
        assert client.post("/api/platform/enroll/start", json={
            "username": username, "enrollmentToken": token,
        }).status_code == 401
        return secret

    def login(client, username, password, secret):
        response = client.post("/api/platform/session", json={
            "username": username, "password": password, "code": code_for(secret),
        })
        assert response.status_code == 200, response.text
        return {"X-Platform-Session": response.json()["token"]}

    try:
        with TestClient(app) as client:
            assert client.get("/api/platform/companies", headers={
                "X-Platform-Key": bootstrap_key,
            }).status_code == 401
            bootstrap = client.post("/api/platform/bootstrap", json={
                "username": "main-owner", "key": bootstrap_key, "code": code_for(bootstrap_secret),
            })
            assert bootstrap.status_code == 200, bootstrap.text
            owner_secret = enroll(client, "main-owner", bootstrap.json()["enrollmentToken"], "owner-long-password-2026")
            assert client.post("/api/platform/bootstrap", json={
                "username": "second-owner", "key": bootstrap_key, "code": code_for(bootstrap_secret),
            }).status_code == 409
            assert client.get("/api/platform/companies", headers={
                "X-Platform-Key": bootstrap_key,
            }).status_code == 401
            assert client.post("/api/platform/session", json={
                "key": bootstrap_key, "code": code_for(bootstrap_secret),
            }).status_code == 401
            assert client.post("/api/platform/session", json={
                "username": "main-owner", "password": "wrong-password", "code": code_for(owner_secret),
            }).status_code == 401

            owner = login(client, "main-owner", "owner-long-password-2026", owner_secret)
            assert client.get("/api/platform/me", headers=owner).json() == {
                "username": "main-owner", "role": "superadmin", "individual": True,
            }
            new_cafe = client.post("/api/platform/companies", headers=owner, json={
                "slug": "admin-audit-test", "name": "Audit Cafe",
                "ownerName": "Cafe Owner", "ownerPin": "1234",
            })
            assert new_cafe.status_code == 201, new_cafe.text
            cid = new_cafe.json()["id"]

            invite_mgr = client.post("/api/platform/admins", headers=owner, json={
                "username": "shop-manager", "role": "manager",
            })
            assert invite_mgr.status_code == 201, invite_mgr.text
            manager_secret = enroll(client, "shop-manager", invite_mgr.json()["enrollmentToken"], "manager-long-password-2026")
            manager = login(client, "shop-manager", "manager-long-password-2026", manager_secret)
            assert client.put("/api/platform/pricing", headers=manager, json={
                "monthly": 200000, "yearly": 2000000,
            }).status_code == 403

            grant = client.post(f"/api/platform/companies/{cid}/subscription/extend", headers=manager, json={
                "period": "monthly", "operationId": "admin-audit-grant-0123456",
            })
            assert grant.status_code == 200, grant.text
            assert grant.json()["subscription"]["plan"] == "monthly"
            history = client.get(f"/api/platform/companies/{cid}/license-history", headers=manager)
            assert history.status_code == 200
            assert history.json()[0]["actor"] == "shop-manager"
            assert history.json()[0]["details"]["after"]["plan"] == "monthly"

            invite_auditor = client.post("/api/platform/admins", headers=owner, json={
                "username": "report-auditor", "role": "auditor",
            })
            assert invite_auditor.status_code == 201
            auditor_secret = enroll(client, "report-auditor", invite_auditor.json()["enrollmentToken"], "auditor-long-password-2026")
            auditor = login(client, "report-auditor", "auditor-long-password-2026", auditor_secret)
            assert client.get("/api/platform/companies", headers=auditor).status_code == 200
            assert client.post(f"/api/platform/companies/{cid}/subscription/extend", headers=auditor, json={
                "period": "yearly", "operationId": "auditor-denied-012345678",
            }).status_code == 403
            assert client.get("/api/platform/admins", headers=auditor).status_code == 403
            assert client.get("/api/platform/audit", headers=auditor).status_code == 403

            admins = client.get("/api/platform/admins", headers=owner).json()
            mgr_id = next(a["id"] for a in admins if a["username"] == "shop-manager")
            main_id = next(a["id"] for a in admins if a["username"] == "main-owner")
            assert client.patch(f"/api/platform/admins/{main_id}", headers=owner, json={
                "active": False,
            }).status_code == 409
            change = client.patch(f"/api/platform/admins/{mgr_id}", headers=owner, json={
                "active": False,
            })
            assert change.status_code == 200
            assert client.get("/api/platform/companies", headers=manager).status_code == 401
            reset = client.post(f"/api/platform/admins/{mgr_id}/reset", headers=owner)
            assert reset.status_code == 200
            new_manager_secret = enroll(client, "shop-manager", reset.json()["enrollmentToken"], "new-manager-password-2026")
            renewed_manager = login(client, "shop-manager", "new-manager-password-2026", new_manager_secret)
            assert client.get("/api/platform/companies", headers=renewed_manager).status_code == 200

            audited = client.get("/api/platform/audit?limit=5", headers=owner)
            assert audited.status_code == 200
            assert len(audited.json()["events"]) == 5
            assert audited.json()["nextBeforeId"] is not None
            assert all(event["actor"] for event in audited.json()["events"])
            with factory() as db:
                saved = db.scalars(select(PlatformAudit)).all()
                assert any(a.action == "admin_updated" and a.details["actor"] == "main-owner" for a in saved)
                assert any(a.action == "extend_monthly" and a.details["actor"] == "shop-manager"
                           and a.details["companyId"] == cid for a in saved)
                assert db.scalar(select(LicenseAudit).where(LicenseAudit.company_id == cid)).actor_username

            assert client.post("/api/platform/logout", headers=owner).status_code == 200
            assert client.get("/api/platform/companies", headers=owner).status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_offline_recovery_requires_operator_and_revokes_sessions(monkeypatch, capsys):
    import sys
    from app import recover_platform_admin as recovery
    from app.db import PlatformAdmin
    from app.platform_security import _password_hash
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(recovery, "SessionLocal", factory)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./TEST_ONLY_DB")
    monkeypatch.setenv("PLATFORM_MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with factory() as db:
        db.add(PlatformAdmin(
            username="lost-superadmin", role="superadmin", active=True,
            password_hash=_password_hash("old-long-password"),
            totp_encrypted="encrypted-test-seed", session_version=3,
        ))
        db.commit()

    monkeypatch.setattr(sys, "argv", ["recover", "--username", "lost-superadmin",
                                      "--confirm", "RECOVER-PLATFORM-ADMIN"])
    monkeypatch.delenv("PLATFORM_RECOVERY_MODE", raising=False)
    try:
        recovery.main()
        raise AssertionError("Recovery should require explicit server consent")
    except SystemExit as exc:
        assert exc.code == 2
    monkeypatch.setenv("PLATFORM_RECOVERY_MODE", "1")
    assert recovery.main() == 0
    token = capsys.readouterr().out.strip()
    assert len(token) >= 40
    with factory() as db:
        admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.username == "lost-superadmin"))
        assert admin.active is False
        assert admin.session_version == 4
        assert admin.password_hash is None
        assert admin.invite_hash == hashlib.sha256(token.encode()).hexdigest()
    engine.dispose()
