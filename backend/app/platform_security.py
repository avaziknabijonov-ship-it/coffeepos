"""Platform administrator bootstrap login with optional TOTP MFA.

The platform never accepts cafe PINs/tokens. On commercial deployments,
PLATFORM_REQUIRE_MFA=1 and PLATFORM_ADMIN_TOTP_SECRET must be configured.
Admin sessions expire after 15 minutes and are invalidated by key rotation.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

import jwt
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field

from .security import LoginLimiter

ADMIN_SESSION_TTL = 15 * 60
_login_limiter = LoginLimiter(max_fails=6, window=300)


class PlatformLogin(BaseModel):
    key: str = Field(min_length=1, max_length=512)
    code: str = Field(default="", max_length=12)


def _admin_key() -> str:
    return os.environ.get("PLATFORM_ADMIN_KEY", "")


def _mfa_secret() -> str:
    return os.environ.get("PLATFORM_ADMIN_TOTP_SECRET", "").strip()


def _mfa_enabled() -> bool:
    return os.environ.get("PLATFORM_REQUIRE_MFA", "0") == "1" or bool(_mfa_secret())


def _session_secret(key: str) -> bytes:
    # Separate domain from staff tokens. Rotation of the server-side key
    # immediately invalidates all platform sessions.
    return hashlib.sha256(("coffeepos-platform-admin-session-v1:" + key).encode()).digest()


def _totp_valid(code: str, base32_secret: str) -> bool:
    if not (len(code) == 6 and code.isascii() and code.isdigit()):
        return False
    try:
        padded = base32_secret.upper() + "=" * (-len(base32_secret) % 8)
        secret = base64.b32decode(padded, casefold=True)
        if len(secret) < 16:
            return False
    except (ValueError, base64.binascii.Error):
        return False
    step = int(time.time() // 30)
    for counter in (step - 1, step, step + 1):
        digest = hmac.new(secret, struct.pack(">Q", counter), "sha1").digest()
        offset = digest[-1] & 15
        number = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
        if secrets.compare_digest(f"{number:06d}", code):
            return True
    return False


def create_platform_session(body: PlatformLogin, request: Request) -> dict:
    key = _admin_key()
    client_host = request.client.host if request.client else "unknown"
    identity = f"platform:{client_host}"
    if _login_limiter.blocked(identity):
        raise HTTPException(429, "Too many platform login attempts. Try again later.")

    valid_key = len(key) >= 32 and secrets.compare_digest(key, body.key)
    otp_secret = _mfa_secret()
    if _mfa_enabled() and not otp_secret:
        # Fail closed: a server requiring MFA must not silently fall back.
        raise HTTPException(503, "Platform MFA is not configured")
    valid_otp = not _mfa_enabled() or _totp_valid(body.code, otp_secret)
    if not valid_key or not valid_otp:
        _login_limiter.fail(identity)
        raise HTTPException(401, "Invalid platform administrator credentials")

    _login_limiter.reset(identity)
    now = int(time.time())
    token = jwt.encode({
        "sub": "platform-admin",
        "scope": "coffeepos:platform",
        "iat": now,
        "exp": now + ADMIN_SESSION_TTL,
        "nonce": secrets.token_urlsafe(12),
    }, _session_secret(key), algorithm="HS256")
    return {"token": token, "expiresAt": (now + ADMIN_SESSION_TTL) * 1000, "mfaEnabled": _mfa_enabled()}


def platform_auth(
    x_platform_session: str = Header(default=""),
    x_platform_key: str = Header(default=""),
) -> None:
    key = _admin_key()
    if len(key) < 32:
        raise HTTPException(401, "Platform administrator access required")
    if x_platform_session:
        try:
            claims = jwt.decode(x_platform_session, _session_secret(key), algorithms=["HS256"])
            if claims.get("sub") == "platform-admin" and claims.get("scope") == "coffeepos:platform":
                return
        except jwt.PyJWTError:
            pass
        raise HTTPException(401, "Platform session expired or invalid")
    # Legacy direct-key access is only for local/testing deployments WITHOUT
    # configured MFA. Commercial MFA-enabled servers require a session token.
    if not _mfa_enabled() and x_platform_key and secrets.compare_digest(key, x_platform_key):
        return
    raise HTTPException(401, "Platform administrator access required")
