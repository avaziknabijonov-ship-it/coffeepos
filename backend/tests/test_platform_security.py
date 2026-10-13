"""Platform bootstrap sessions and authenticator MFA; in-memory test DB only."""
import base64
import hmac
import hashlib
import struct
import time

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.platform import get_db as platform_db
from app.platform_security import _session_secret


def _totp_code(secret: bytes) -> str:
    digest = hmac.new(secret, struct.pack(">Q", int(time.time() // 30)), "sha1").digest()
    offset = digest[-1] & 15
    return f"{(struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff) % 1000000:06d}"


def test_platform_requires_authenticator_and_expires_session(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override():
        with factory() as db:
            yield db

    key = "secure-test-admin-key-" + "z" * 40
    raw_totp = b"test-platform-secret-0123456789"
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", key)
    monkeypatch.setenv("PLATFORM_ADMIN_TOTP_SECRET", base64.b32encode(raw_totp).decode())
    monkeypatch.setenv("PLATFORM_REQUIRE_MFA", "1")
    app.dependency_overrides[platform_db] = override
    try:
        with TestClient(app) as client:
            assert client.get("/api/platform/companies", headers={
                "X-Platform-Key": key,
            }).status_code == 401
            assert client.post("/api/platform/session", json={
                "key": key, "code": "not-a-code",
            }).status_code == 401
            assert client.post("/api/platform/session", json={
                "key": "wrong-key", "code": _totp_code(raw_totp),
            }).status_code == 401

            login = client.post("/api/platform/session", json={
                "key": key, "code": _totp_code(raw_totp),
            })
            assert login.status_code == 200, login.text
            token = login.json()["token"]
            assert login.json()["mfaEnabled"] is True
            assert client.get("/api/platform/companies", headers={
                "X-Platform-Session": token,
            }).status_code == 200

            expired = jwt.encode({
                "sub": "platform-admin", "scope": "coffeepos:platform",
                "exp": int(time.time()) - 30,
            }, _session_secret(key), algorithm="HS256")
            assert client.get("/api/platform/companies", headers={
                "X-Platform-Session": expired,
            }).status_code == 401

            # Rotating the administrator key immediately invalidates sessions.
            monkeypatch.setenv("PLATFORM_ADMIN_KEY", "new-admin-key-" + "r" * 40)
            assert client.get("/api/platform/companies", headers={
                "X-Platform-Session": token,
            }).status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
