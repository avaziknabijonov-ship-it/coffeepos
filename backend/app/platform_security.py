"""Individual CoffeePOS platform admins: enrollment, roles, password + TOTP, revocable sessions."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
import jwt
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import PlatformAdmin, PlatformAudit, now_ms
from .security import LoginLimiter

ADMIN_SESSION_TTL = 15 * 60
ENROLLMENT_TTL_MS = 24 * 60 * 60 * 1000
PASSWORD_ITERATIONS = 360_000
USERNAME_RE = r"^[a-z][a-z0-9._-]{2,39}$"
_login_limiter = LoginLimiter(max_fails=6, window=300)


@dataclass(frozen=True)
class PlatformActor:
    id: int | None
    username: str
    role: str


class PlatformLogin(BaseModel):
    key: str | None = Field(default=None, max_length=512)
    username: str | None = Field(default=None, max_length=40)
    password: str | None = Field(default=None, max_length=256)
    code: str = Field(default="", max_length=12)


class BootstrapAdmin(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=USERNAME_RE)
    key: str = Field(min_length=1, max_length=512)
    code: str = Field(default="", max_length=12)


class CreateAdmin(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=USERNAME_RE)
    role: str = Field(pattern=r"^(superadmin|manager|auditor)$")


class EnrollRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    enrollmentToken: str = Field(min_length=40, max_length=128)


class FinishEnrollment(EnrollRequest):
    password: str = Field(min_length=12, max_length=128)
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


class EditAdmin(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(superadmin|manager|auditor)$")
    active: bool | None = None


def _admin_key() -> str:
    return os.environ.get("PLATFORM_ADMIN_KEY", "")


def _mfa_secret() -> str:
    return os.environ.get("PLATFORM_ADMIN_TOTP_SECRET", "").strip()


def _mfa_enabled() -> bool:
    return os.environ.get("PLATFORM_REQUIRE_MFA", "0") == "1" or bool(_mfa_secret())


def _account_required() -> bool:
    return os.environ.get("PLATFORM_REQUIRE_ADMIN_ACCOUNTS", "0") == "1"


def _session_secret(key: str) -> bytes:
    return hashlib.sha256(("coffeepos-platform-admin-session-v1:" + key).encode()).digest()


def _cipher() -> Fernet:
    value = os.environ.get("PLATFORM_MFA_ENCRYPTION_KEY", "")
    try:
        return Fernet(value.encode("ascii"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise HTTPException(503, "Platform MFA encryption key is not configured") from exc


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


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return salt.hex() + "$" + digest.hex()


def _password_matches(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PASSWORD_ITERATIONS)
        return hmac.compare_digest(candidate, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def _totp_seed() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _read_totp(admin: PlatformAdmin) -> str:
    try:
        return _cipher().decrypt(admin.totp_encrypted.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise HTTPException(503, "Administrator MFA recovery is required") from exc


def has_admins(db: Session) -> bool:
    return db.scalar(select(PlatformAdmin.id).limit(1)) is not None


def _rate_limit(request: Request, name: str) -> str:
    host = request.client.host if request.client else "unknown"
    rate_id = f"platform:{host}:{name}"
    if _login_limiter.blocked(rate_id):
        raise HTTPException(429, "Too many administrator attempts. Try later.")
    return rate_id


def _bootstrap_allowed(key: str | None, code: str, request: Request) -> None:
    rate_id = _rate_limit(request, "bootstrap")
    env_key = _admin_key()
    if len(env_key) < 32 or not key or not secrets.compare_digest(env_key, key):
        _login_limiter.fail(rate_id)
        raise HTTPException(401, "Invalid platform bootstrap credentials")
    if _mfa_enabled() and not _mfa_secret():
        raise HTTPException(503, "Platform bootstrap MFA is not configured")
    if _mfa_enabled() and not _totp_valid(code, _mfa_secret()):
        _login_limiter.fail(rate_id)
        raise HTTPException(401, "Invalid platform bootstrap credentials")
    _login_limiter.reset(rate_id)


def audit(db: Session, action: str, actor: str, request: Request | None = None, **details: object) -> None:
    db.add(PlatformAudit(action=action, details={
        "actor": actor,
        "ip": request.client.host if request and request.client else "system",
        **details,
    }))


def _issue_invitation(db: Session, username: str, role: str) -> tuple[PlatformAdmin, str]:
    token = secrets.token_urlsafe(36)
    secret = _totp_seed()
    admin = PlatformAdmin(
        username=username, role=role,
        totp_encrypted=_cipher().encrypt(secret.encode("ascii")).decode("ascii"),
        invite_hash=hashlib.sha256(token.encode()).hexdigest(),
        invite_expires_at=now_ms() + ENROLLMENT_TTL_MS,
        active=False, password_hash=None,
    )
    db.add(admin)
    db.flush()
    return admin, token


def bootstrap_admin(db: Session, body: BootstrapAdmin, request: Request) -> dict:
    if has_admins(db):
        raise HTTPException(409, "Initial Super Admin has already been created")
    _bootstrap_allowed(body.key, body.code, request)
    admin, token = _issue_invitation(db, body.username, "superadmin")
    audit(db, "admin_bootstrap", "bootstrap", request, username=body.username)
    db.commit()
    return {"username": admin.username, "enrollmentToken": token, "expiresAt": admin.invite_expires_at}


def new_admin(db: Session, username: str, role: str, actor: PlatformActor, request: Request) -> dict:
    if db.scalar(select(PlatformAdmin.id).where(PlatformAdmin.username == username)):
        raise HTTPException(409, "Administrator username already exists")
    admin, token = _issue_invitation(db, username, role)
    audit(db, "admin_invited", actor.username, request, username=username, role=role)
    db.commit()
    return {"id": admin.id, "username": username, "role": role,
            "enrollmentToken": token, "expiresAt": admin.invite_expires_at}


def _invited_admin(db: Session, body: EnrollRequest) -> PlatformAdmin:
    admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.username == body.username))
    expected = hashlib.sha256(body.enrollmentToken.encode()).hexdigest()
    if (not admin or not admin.invite_hash or not secrets.compare_digest(admin.invite_hash, expected)
            or not admin.invite_expires_at or admin.invite_expires_at < now_ms()):
        raise HTTPException(401, "Invalid or expired administrator invitation")
    return admin


def start_enrollment(db: Session, body: EnrollRequest, request: Request) -> dict:
    _rate_limit(request, body.username)
    admin = _invited_admin(db, body)
    secret = _read_totp(admin)
    uri = f"otpauth://totp/{quote('CoffeePOS:' + admin.username)}?secret={secret}&issuer=CoffeePOS&digits=6&period=30"
    return {"username": admin.username, "totpSecret": secret, "otpauthUri": uri}


def finish_enrollment(db: Session, body: FinishEnrollment, request: Request) -> dict:
    rate_id = _rate_limit(request, body.username)
    admin = _invited_admin(db, body)
    if not _totp_valid(body.code, _read_totp(admin)):
        _login_limiter.fail(rate_id)
        raise HTTPException(401, "Invalid administrator authenticator code")
    admin.password_hash = _password_hash(body.password)
    admin.invite_hash = None
    admin.invite_expires_at = None
    admin.active = True
    admin.session_version += 1
    audit(db, "admin_enrolled", admin.username, request, role=admin.role)
    db.commit()
    _login_limiter.reset(rate_id)
    return {"username": admin.username, "active": True}


def create_platform_session(body: PlatformLogin, request: Request, db: Session | None = None) -> dict:
    key = _admin_key()
    if db is not None and has_admins(db):
        username = (body.username or "").lower().strip()
        rate_id = _rate_limit(request, username)
        admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.username == username))
        password_ok = bool(admin and admin.password_hash and body.password and
                           _password_matches(body.password, admin.password_hash))
        otp_ok = bool(admin and admin.active and password_ok and _totp_valid(body.code, _read_totp(admin)))
        if not otp_ok:
            _login_limiter.fail(rate_id)
            raise HTTPException(401, "Invalid administrator credentials")
        if len(key) < 32:
            raise HTTPException(503, "Platform session signing key is not configured")
        _login_limiter.reset(rate_id)
        now = int(time.time())
        claims = {
            "sub": f"admin:{admin.id}", "scope": "coffeepos:platform",
            "version": admin.session_version,
            "mfa": True, "iat": now, "exp": now + ADMIN_SESSION_TTL,
            "nonce": secrets.token_urlsafe(12),
        }
        token = jwt.encode(claims, _session_secret(key), algorithm="HS256")
        admin.last_login_at = now_ms()
        audit(db, "admin_login", admin.username, request, role=admin.role)
        db.commit()
        return {"token": token, "expiresAt": (now + ADMIN_SESSION_TTL) * 1000,
                "mfaEnabled": True, "actor": {"username": admin.username, "role": admin.role}}
    if _account_required():
        raise HTTPException(403, "Create the initial administrator account first")
    _bootstrap_allowed(body.key, body.code, request)
    now = int(time.time())
    token = jwt.encode({
        "sub": "platform-admin", "scope": "coffeepos:platform", "iat": now,
        "exp": now + ADMIN_SESSION_TTL, "nonce": secrets.token_urlsafe(12), "mfa": _mfa_enabled(),
    }, _session_secret(key), algorithm="HS256")
    if db is not None:
        audit(db, "bootstrap_login", "bootstrap", request)
        db.commit()
    return {"token": token, "expiresAt": (now + ADMIN_SESSION_TTL) * 1000,
            "mfaEnabled": _mfa_enabled(), "actor": {"username": "bootstrap", "role": "superadmin"}}


def platform_auth(db: Session, x_platform_session: str = "", x_platform_key: str = "") -> PlatformActor:
    key = _admin_key()
    if len(key) < 32:
        raise HTTPException(401, "Platform authentication unavailable")
    managed = has_admins(db)
    if x_platform_session:
        try:
            claims = jwt.decode(x_platform_session, _session_secret(key), algorithms=["HS256"])
            if claims.get("scope") != "coffeepos:platform":
                raise HTTPException(401, "Invalid administrator session")
            sub = claims.get("sub", "")
            if managed:
                if not sub.startswith("admin:") or claims.get("mfa") is not True:
                    raise HTTPException(401, "Individual administrator session required")
                admin = db.get(PlatformAdmin, int(sub.removeprefix("admin:")))
                if not admin or not admin.active or not admin.password_hash or admin.session_version != claims.get("version"):
                    raise HTTPException(401, "Administrator account disabled or session revoked")
                return PlatformActor(admin.id, admin.username, admin.role)
            if not _account_required() and sub == "platform-admin" and (not _mfa_enabled() or claims.get("mfa") is True):
                return PlatformActor(None, "bootstrap", "superadmin")
        except (jwt.PyJWTError, ValueError):
            pass
        raise HTTPException(401, "Platform session expired or invalid")
    if not managed and not _account_required() and not _mfa_enabled() and x_platform_key and secrets.compare_digest(key, x_platform_key):
        return PlatformActor(None, "bootstrap", "superadmin")
    raise HTTPException(401, "Individual platform administrator login required")


def require_role(actor: PlatformActor, allowed: tuple[str, ...]) -> None:
    if actor.role not in allowed:
        raise HTTPException(403, "This administrator does not have permission")


def ensure_last_superadmin(db: Session, admin: PlatformAdmin) -> None:
    if admin.role != "superadmin" or not admin.active:
        return
    other = db.scalar(select(PlatformAdmin.id).where(
        PlatformAdmin.id != admin.id, PlatformAdmin.role == "superadmin",
        PlatformAdmin.active.is_(True),
    ).limit(1))
    if other is None:
        raise HTTPException(409, "Cannot disable or demote the last active Super Admin")
