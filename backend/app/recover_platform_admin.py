"""Emergency recovery for a lost initial platform MFA device.

Run ONLY with shell access to the correct server, explicitly setting the
production DATABASE_URL and PLATFORM_RECOVERY_MODE=1. There is no public
recovery HTTP endpoint. The tool changes only the named administrator account.
"""
import argparse
import hashlib
import os
import secrets
import sys

from sqlalchemy import select

from .db import PlatformAdmin, PlatformAudit, SessionLocal, now_ms
from .platform_security import _cipher, _totp_seed, ENROLLMENT_TTL_MS


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue a fresh enrollment invite after losing all Super Admin access")
    parser.add_argument("--username", required=True)
    parser.add_argument("--confirm", required=True, help="Must be exactly RECOVER-PLATFORM-ADMIN")
    args = parser.parse_args()
    if os.environ.get("PLATFORM_RECOVERY_MODE") != "1" or args.confirm != "RECOVER-PLATFORM-ADMIN":
        parser.error("Offline recovery requires PLATFORM_RECOVERY_MODE=1 and explicit confirmation")
    if not os.environ.get("DATABASE_URL"):
        parser.error("Explicit DATABASE_URL is required. Refusing to use the default coffee database.")
    with SessionLocal() as db:
        admin = db.scalar(select(PlatformAdmin).where(PlatformAdmin.username == args.username).with_for_update())
        if not admin:
            parser.error("Administrator username not found. No changes made.")
        if admin.role != "superadmin":
            parser.error("This offline recovery works for Super Admin accounts only.")
        other = db.scalar(select(PlatformAdmin.id).where(
            PlatformAdmin.id != admin.id,
            PlatformAdmin.role == "superadmin", PlatformAdmin.active.is_(True),
        ).limit(1))
        if other:
            parser.error("Another active Super Admin exists; ask them to reset this account via the dashboard.")
        # A server operator must be able to recover an expired first-invite even
        # when there are no active Super Admin accounts.
        token = secrets.token_urlsafe(36)
        admin.totp_encrypted = _cipher().encrypt(_totp_seed().encode("ascii")).decode("ascii")
        admin.invite_hash = hashlib.sha256(token.encode()).hexdigest()
        admin.invite_expires_at = now_ms() + ENROLLMENT_TTL_MS
        admin.password_hash = None
        admin.active = False
        admin.session_version += 1
        db.add(PlatformAudit(action="offline_admin_recovery", details={
            "actor": "server-console-recovery",
            "username": admin.username,
            "reason": "No other active Super Admin",
        }))
        db.commit()
        print("Administrator:", admin.username, file=sys.stderr)
        print("The next enrollment token is shown ONCE. Treat it as a password.", file=sys.stderr)
        print(token)  # Redirect stdout to an appropriately protected local file.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
