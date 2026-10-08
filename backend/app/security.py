import hashlib
import hmac
import os
import secrets
import time

import jwt
from sqlalchemy.orm import Session

from .db import Setting

TOKEN_TTL = 16 * 3600
_ITER = 120_000


def hash_pin(pin: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), _ITER).hex()
    return f"{salt}${digest}"


def check_pin(pin: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    candidate = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), _ITER).hex()
    return hmac.compare_digest(candidate, digest)


def secret_key(db: Session) -> str:
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    row = db.get(Setting, "secret_key")
    if not row:
        row = Setting(key="secret_key", value=secrets.token_urlsafe(48))
        db.add(row)
        db.commit()
    return row.value


def make_token(db: Session, staff_id: int, company_id: int) -> str:
    payload = {"sub": str(staff_id), "cid": company_id, "exp": int(time.time()) + TOKEN_TTL}
    return jwt.encode(payload, secret_key(db), algorithm="HS256")


def read_token(db: Session, token: str) -> dict | None:
    try:
        return jwt.decode(token, secret_key(db), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


class LoginLimiter:
    """Blocks a company+client pair after too many wrong PINs."""

    def __init__(self, max_fails: int = 8, window: int = 300):
        self.max_fails = max_fails
        self.window = window
        self.fails: dict[str, list[float]] = {}

    def blocked(self, key: str) -> bool:
        now = time.time()
        recent = [t for t in self.fails.get(key, []) if now - t < self.window]
        self.fails[key] = recent
        return len(recent) >= self.max_fails

    def fail(self, key: str) -> None:
        self.fails.setdefault(key, []).append(time.time())

    def reset(self, key: str) -> None:
        self.fails.pop(key, None)
