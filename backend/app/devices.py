"""Device registry (identity, branch binding, revoke, last seen) and client release rollout."""
import hashlib
import hmac
import os
import re
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import record as audit_record
from .core import MANAGERS, Ctx, auth, get_db, require
from .db import AppRelease, Branch, Device, DevicePolicy, now_ms

router = APIRouter()
BACKEND_VERSION = "1.0.0"
SEMVER = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"


def parse(version: str) -> tuple[int, int, int]:
    m = re.fullmatch(SEMVER, version or "")
    if not m:
        raise ValueError("Semantic version required")
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def resolve_device(db: Session, cid: int, token: str) -> Device:
    device = db.scalar(select(Device).where(Device.secret_hash == hash_secret(token)))
    if device is None or device.company_id != cid or device.revoked_at is not None:
        raise HTTPException(401, "Qurilma ro‘yxatdan o‘tmagan yoki bloklangan")
    return device


def touch(device: Device, version: str) -> None:
    now = now_ms()
    if device.last_seen_at is None or now - device.last_seen_at > 60_000 or (version and version != device.app_version):
        device.last_seen_at = now
        if version:
            device.app_version = version[:32]


def device_required(db: Session, cid: int) -> bool:
    policy = db.get(DevicePolicy, cid)
    return bool(policy and policy.require_device)


class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: Literal["pos", "kds", "apk", "admin"] = "pos"
    branchId: int | None = None


def device_out(d: Device) -> dict:
    return {"id": d.id, "name": d.name, "kind": d.kind, "branchId": d.branch_id, "appVersion": d.app_version,
            "lastSeenAt": d.last_seen_at, "revokedAt": d.revoked_at, "createdAt": d.created_at}


@router.post("/api/devices", status_code=201)
def register_device(body: DeviceIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    if body.branchId is not None:
        branch = ctx.db.get(Branch, body.branchId)
        if branch is None or branch.company_id != ctx.cid:
            raise HTTPException(404, "Filial topilmadi")
        if ctx.staff.branch_id is not None and branch.id != ctx.staff.branch_id:
            raise HTTPException(403, "Bu filial uchun ruxsat yo'q")
    secret = "dev_" + secrets.token_urlsafe(32)
    device = Device(company_id=ctx.cid, branch_id=body.branchId, name=body.name.strip(), kind=body.kind,
                    secret_hash=hash_secret(secret))
    ctx.db.add(device)
    ctx.db.flush()
    audit_record(ctx, "device.register", device.id, {}, {"name": device.name, "branchId": device.branch_id})
    ctx.db.commit()
    return {**device_out(device), "token": secret}  # Shown once; store it on the device only.


@router.get("/api/devices")
def list_devices(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(Device).where(Device.company_id == ctx.cid).order_by(Device.id)
    return [device_out(d) for d in ctx.db.scalars(q)]


@router.post("/api/devices/{device_id}/revoke")
def revoke_device(device_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    device = ctx.db.get(Device, device_id)
    if device is None or device.company_id != ctx.cid:
        raise HTTPException(404, "Qurilma topilmadi")
    if device.revoked_at is None:
        device.revoked_at = now_ms()
        audit_record(ctx, "device.revoke", device.id, {"status": "active"}, {"status": "revoked"})
        ctx.db.commit()
    return device_out(device)


class PolicyIn(BaseModel):
    requireDevice: bool


@router.put("/api/devices/policy")
def set_policy(body: PolicyIn, ctx: Ctx = Depends(require("owner"))) -> dict:
    policy = ctx.db.get(DevicePolicy, ctx.cid) or DevicePolicy(company_id=ctx.cid)
    ctx.db.add(policy)
    policy.require_device = body.requireDevice
    audit_record(ctx, "device.policy", ctx.cid, {}, {"status": "required" if body.requireDevice else "optional"})
    ctx.db.commit()
    return {"requireDevice": policy.require_device}


# ---------- releases ----------
def platform_admin(x_superadmin_key: str = Header(default="")) -> None:
    """Same platform credential as the superadmin console (SUPERADMIN_KEY, >= 40 chars)."""
    expected = os.environ.get("SUPERADMIN_KEY", "")
    if len(expected) < 40:
        raise HTTPException(503, "Superadmin sozlanmagan")
    if not hmac.compare_digest(expected, x_superadmin_key):
        raise HTTPException(401, "Superadmin ruxsati yo'q")


class ReleaseIn(BaseModel):
    platform: Literal["apk", "web"]
    version: str = Field(pattern=SEMVER)
    minBackend: str = Field(default="0.0.0", pattern=SEMVER)
    minSupported: str = Field(default="0.0.0", pattern=SEMVER)
    rolloutPercent: int = Field(default=10, ge=0, le=100)
    url: str = Field(default="", max_length=512, pattern=r"^(https://.*)?$")
    sha256: str = Field(default="", pattern=r"^([a-f0-9]{64})?$")
    notes: str = Field(default="", max_length=500)


class RolloutIn(BaseModel):
    rolloutPercent: int = Field(ge=0, le=100)


def release_out(r: AppRelease) -> dict:
    return {"id": r.id, "platform": r.platform, "version": r.version, "minBackend": r.min_backend,
            "minSupported": r.min_supported, "rolloutPercent": r.rollout_percent, "status": r.status,
            "url": r.url, "sha256": r.sha256, "notes": r.notes}


@router.post("/api/platform/releases", status_code=201, dependencies=[Depends(platform_admin)])
def create_release(body: ReleaseIn, db: Session = Depends(get_db)) -> dict:
    if parse(body.minSupported) > parse(body.version):
        raise HTTPException(422, "minSupported versiyadan katta bo‘lmasin")
    release = AppRelease(platform=body.platform, version=body.version, min_backend=body.minBackend,
                         min_supported=body.minSupported, rollout_percent=body.rolloutPercent, url=body.url,
                         sha256=body.sha256, notes=body.notes)
    db.add(release)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu versiya allaqachon mavjud") from None
    return release_out(release)


def platform_release(db: Session, release_id: int) -> AppRelease:
    release = db.get(AppRelease, release_id)
    if release is None:
        raise HTTPException(404, "Reliz topilmadi")
    return release


@router.post("/api/platform/releases/{release_id}/rollout", dependencies=[Depends(platform_admin)])
def set_rollout(release_id: int, body: RolloutIn, db: Session = Depends(get_db)) -> dict:
    release = platform_release(db, release_id)
    if release.status != "active":
        raise HTTPException(409, "Orqaga qaytarilgan relizni yoyib bo‘lmaydi")
    release.rollout_percent = body.rolloutPercent
    db.commit()
    return release_out(release)


@router.post("/api/platform/releases/{release_id}/rollback", dependencies=[Depends(platform_admin)])
def rollback_release(release_id: int, db: Session = Depends(get_db)) -> dict:
    release = platform_release(db, release_id)
    release.status, release.rollout_percent = "rolled_back", 0
    db.commit()
    return release_out(release)


def bucket(release: AppRelease, cid: int, subject: str) -> int:
    return int(hashlib.sha256(f"{release.id}:{cid}:{subject}".encode()).hexdigest()[:8], 16) % 100


@router.get("/api/updates/check")
def check_update(platform: Literal["apk", "web"], version: str, ctx: Ctx = Depends(auth)) -> dict:
    try:
        current = parse(version)
    except ValueError:
        raise HTTPException(422, "Versiya formati noto‘g‘ri") from None
    subject = f"d{ctx.device_id}" if ctx.device_id else f"s{ctx.staff.id}"
    releases = ctx.db.scalars(select(AppRelease).where(AppRelease.platform == platform)).all()
    backend = parse(BACKEND_VERSION)
    active = [r for r in releases if r.status == "active" and parse(r.min_backend) <= backend]
    eligible = [r for r in active if parse(r.version) > current and bucket(r, ctx.cid, subject) < r.rollout_percent]
    target = max(eligible, key=lambda r: parse(r.version), default=None)
    min_supported = max((parse(r.min_supported) for r in active), default=(0, 0, 0))
    rolled_back = any(r.status == "rolled_back" and parse(r.version) == current for r in releases)
    if rolled_back and target is None:
        stable = [r for r in active if parse(r.version) < current and r.rollout_percent == 100]
        target = max(stable, key=lambda r: parse(r.version), default=None)
    return {"backendVersion": BACKEND_VERSION, "current": version, "update": release_out(target) if target else None,
            "mandatory": current < min_supported, "rollback": rolled_back and target is not None
            and parse(target.version) < current}
