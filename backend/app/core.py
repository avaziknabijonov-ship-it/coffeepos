"""Shared request context, tenant/branch resolution and RBAC dependencies."""
import os
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Branch, Company, SessionLocal, Shift, Staff, Subscription, now_ms
from .security import read_token

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Tashkent"))
Role = Literal["owner", "admin", "kassir", "barista"]
MANAGERS = ("owner", "admin")
CASHIERS = ("owner", "admin", "kassir")
BARISTAS = ("owner", "admin", "barista")


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Ctx:
    def __init__(self, db: Session, staff: Staff, company: Company, branch: "Branch | None" = None,
                 device_id: int | None = None):
        self.db, self.staff, self.company, self.branch = db, staff, company, branch
        self.device_id = device_id

    @property
    def branch_id(self) -> int | None:
        return self.branch.id if self.branch is not None else None

    @property
    def cid(self) -> int:
        return self.company.id


def default_branch(db: Session, cid: int) -> Branch:
    branch = db.scalar(select(Branch).where(Branch.company_id == cid, Branch.is_default.is_(True)))
    if branch is None:
        branch = Branch(company_id=cid, name="Asosiy filial", is_default=True)
        db.add(branch)
        db.flush()
    return branch


def resolve_branch(db: Session, staff: Staff, requested: str, device_branch_id: int | None = None) -> Branch:
    """Staff bound to a branch always work there; managers may select any active branch."""
    cid = staff.company_id
    if staff.branch_id is not None:
        branch = db.get(Branch, staff.branch_id)
        if branch is None or branch.company_id != cid or not branch.active:
            raise HTTPException(403, "Filial faol emas")
        if requested and requested != str(branch.id):
            raise HTTPException(403, "Bu filial uchun ruxsat yo'q")
        return branch
    if requested:
        if not requested.isdigit():
            raise HTTPException(422, "Filial noto'g'ri")
        branch = db.get(Branch, int(requested))
        if branch is None or branch.company_id != cid or not branch.active:
            raise HTTPException(404, "Filial topilmadi")
        if staff.role not in MANAGERS and branch.id != device_branch_id and branch.id != default_branch(db, cid).id:
            raise HTTPException(403, "Bu filial uchun ruxsat yo'q")
        return branch
    return default_branch(db, cid)


def auth(db: Session = Depends(get_db), authorization: str = Header(default=""),
         x_branch_id: str = Header(default=""), x_device_token: str = Header(default=""),
         x_app_version: str = Header(default="")) -> Ctx:
    claims = read_token(db, authorization.removeprefix("Bearer ").strip()) if authorization else None
    if not claims:
        raise HTTPException(401, "Qaytadan kiring")
    staff = db.get(Staff, int(claims["sub"]))
    if not staff or not staff.active or staff.company_id != claims["cid"]:
        raise HTTPException(401, "Qaytadan kiring")
    if os.environ.get("ENFORCE_LICENSES", "0") == "1":
        subscription = db.get(Subscription, staff.company_id)
        if not subscription or subscription.status != "active" or subscription.expires_at <= now_ms():
            raise HTTPException(403, "Obuna faol emas. Administratorga murojaat qiling")
    from . import devices  # local import: devices depends on this module
    minimum = os.environ.get("MIN_CLIENT_VERSION", "")
    if minimum and x_app_version:
        try:
            if devices.parse(x_app_version.strip()) < devices.parse(minimum):
                raise HTTPException(426, "Ilovani yangilang")
        except ValueError:
            raise HTTPException(426, "Ilova versiyasi noto‘g‘ri") from None
    requested = x_branch_id.strip()
    device = None
    if x_device_token:
        device = devices.resolve_device(db, staff.company_id, x_device_token.strip())
        if device.branch_id is not None:
            if requested and requested != str(device.branch_id):
                raise HTTPException(403, "Qurilma boshqa filialga biriktirilgan")
            requested = str(device.branch_id)
        devices.touch(device, x_app_version.strip())
        db.commit()
    elif staff.role != "owner" and devices.device_required(db, staff.company_id):
        raise HTTPException(401, "Bu kompaniyada faqat ro‘yxatdan o‘tgan qurilmalar ishlaydi")
    branch = resolve_branch(db, staff, requested, device.branch_id if device else None)
    return Ctx(db, staff, db.get(Company, staff.company_id), branch,
               device.id if device else claims.get("did"))


def require(*roles: str):
    def dep(ctx: Ctx = Depends(auth)) -> Ctx:
        if ctx.staff.role not in roles:
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
        return ctx

    return dep


def rows(db: Session, model, cid: int):
    return db.scalars(select(model).where(model.company_id == cid).order_by(model.id)).all()


def get_row(db: Session, model, cid: int, key: str):
    row = db.scalar(select(model).where(model.company_id == cid, model.key == key))
    if not row:
        raise HTTPException(404, "Topilmadi")
    return row


def open_shift(db: Session, cid: int, branch_id: int | None = None) -> Shift | None:
    """Open shift of a branch (None = default branch, kept for older call sites)."""
    if branch_id is None:
        branch_id = default_branch(db, cid).id
    return db.scalar(select(Shift).where(Shift.company_id == cid, Shift.branch_id == branch_id,
                                         Shift.closed_at.is_(None)))


def start_of_day_ms(days_ago: int = 0) -> int:
    d = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return int(d.timestamp() * 1000)




def enabled_modules(db: Session, cid: int) -> list[str]:
    """Optional modules always require a live license, even when core license enforcement is off."""
    sub = db.get(Subscription, cid)
    if sub is None or sub.status != "active" or sub.expires_at <= now_ms():
        return []
    return [name for name in (sub.modules or []) if name in {"hookah"}]
