"""Branch (filial) management and branch-scoped stock views."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import stock as branch_stock
from .audit import record as audit_record
from .core import MANAGERS, Ctx, auth, require, rows
from .db import Branch, Ingredient, Staff

router = APIRouter()


def branch_out(b: Branch) -> dict:
    return {"id": b.id, "name": b.name, "isDefault": bool(b.is_default), "active": bool(b.active)}


class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class BranchPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    active: bool | None = None


class StaffBranchIn(BaseModel):
    branchId: int | None = None


def company_branch(ctx: Ctx, branch_id: int) -> Branch:
    branch = ctx.db.get(Branch, branch_id)
    if branch is None or branch.company_id != ctx.cid:
        raise HTTPException(404, "Filial topilmadi")
    return branch


@router.get("/api/branches")
def list_branches(ctx: Ctx = Depends(auth)) -> dict:
    visible = rows(ctx.db, Branch, ctx.cid)
    if ctx.staff.branch_id is not None:
        visible = [b for b in visible if b.id == ctx.staff.branch_id]
    return {"current": ctx.branch_id, "items": [branch_out(b) for b in visible]}


@router.post("/api/branches", status_code=201)
def create_branch(body: BranchIn, ctx: Ctx = Depends(require("owner"))) -> dict:
    branch = Branch(company_id=ctx.cid, name=body.name.strip(), is_default=False, active=True)
    ctx.db.add(branch)
    try:
        ctx.db.flush()
    except IntegrityError:
        ctx.db.rollback()
        raise HTTPException(409, "Bu nomli filial bor") from None
    audit_record(ctx, "branch.create", branch.id, {}, branch_out(branch))
    ctx.db.commit()
    return branch_out(branch)


@router.patch("/api/branches/{branch_id}")
def update_branch(branch_id: int, body: BranchPatch, ctx: Ctx = Depends(require("owner"))) -> dict:
    branch = company_branch(ctx, branch_id)
    before = branch_out(branch)
    if body.active is False and branch.is_default:
        raise HTTPException(409, "Asosiy filialni o'chirib bo'lmaydi")
    if body.name is not None:
        branch.name = body.name.strip()
    if body.active is not None:
        branch.active = body.active
    audit_record(ctx, "branch.update", branch.id, before, branch_out(branch))
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise HTTPException(409, "Bu nomli filial bor") from None
    return branch_out(branch)


@router.put("/api/staff/{staff_id}/branch")
def assign_staff_branch(staff_id: int, body: StaffBranchIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    staff = ctx.db.get(Staff, staff_id)
    if staff is None or staff.company_id != ctx.cid:
        raise HTTPException(404, "Xodim topilmadi")
    if staff.role == "owner" and ctx.staff.role != "owner":
        raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
    if body.branchId is not None and not company_branch(ctx, body.branchId).active:
        raise HTTPException(409, "Filial faol emas")
    before = {"branchId": staff.branch_id}
    staff.branch_id = body.branchId
    audit_record(ctx, "staff.branch", staff.id, before, {"branchId": staff.branch_id})
    ctx.db.commit()
    return {"id": staff.id, "branchId": staff.branch_id}


@router.get("/api/branches/{branch_id}/stock")
def branch_stock_levels(branch_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    company_branch(ctx, branch_id)
    if ctx.staff.branch_id is not None and ctx.staff.branch_id != branch_id:
        raise HTTPException(403, "Bu filial uchun ruxsat yo'q")
    names = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    levels = branch_stock.levels(ctx.db, ctx.cid, branch_id)
    return {"branchId": branch_id, "items": [
        {"id": key, "name": names[key].name, "unit": names[key].unit, **level} for key, level in levels.items()
    ]}
