"""Floor plan: areas, tables, occupancy from open drafts, move/merge and takeaway."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .audit import record as audit_record
from .core import CASHIERS, MANAGERS, Ctx, require
from .db import DiningArea, DiningTable, DraftOrder, Staff, now_ms

router = APIRouter()
Service = Literal["takeaway", "dine_in"]


class AreaIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    active: bool = True


class TableIn(BaseModel):
    areaId: int
    name: str = Field(min_length=1, max_length=64)
    seats: int = Field(default=2, ge=1, le=50)
    active: bool = True


class MoveIn(BaseModel):
    version: int = Field(ge=1)
    tableId: int | None = None
    service: Service = "dine_in"


class MergeIn(BaseModel):
    version: int = Field(ge=1)
    targetId: int
    targetVersion: int = Field(ge=1)


def table_out(t: DiningTable, drafts: list[DraftOrder]) -> dict:
    return {"id": t.id, "areaId": t.area_id, "name": t.name, "seats": t.seats, "active": t.active,
            "layout": t.layout, "layoutVersion": t.layout_version, "occupied": bool(drafts), "drafts": [{"id": d.id, "version": d.version, "items": len(d.items),
                                                  "staff": d.staff_name, "updatedAt": d.updated_at} for d in drafts]}


def branch_table(ctx: Ctx, table_id: int) -> DiningTable:
    table = ctx.db.get(DiningTable, table_id)
    if table is None or table.company_id != ctx.cid or table.branch_id != ctx.branch_id:
        raise HTTPException(404, "Stol topilmadi")
    return table


def save(ctx: Ctx, row, action: str, after: dict):
    try:
        ctx.db.flush()
    except IntegrityError:
        ctx.db.rollback()
        raise HTTPException(409, "Bu nom allaqachon mavjud") from None
    audit_record(ctx, action, row.id, {}, after)
    ctx.db.commit()


@router.get("/api/floor")
def floor(ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    areas = ctx.db.scalars(select(DiningArea).where(DiningArea.company_id == ctx.cid,
                                                    DiningArea.branch_id == ctx.branch_id)
                           .order_by(DiningArea.id)).all()
    tables = ctx.db.scalars(select(DiningTable).where(DiningTable.company_id == ctx.cid,
                                                      DiningTable.branch_id == ctx.branch_id)
                            .order_by(DiningTable.id)).all()
    drafts = ctx.db.scalars(select(DraftOrder).where(DraftOrder.company_id == ctx.cid,
                                                     DraftOrder.branch_id == ctx.branch_id)).all()
    by_table: dict[int, list] = {}
    takeaway = []
    for d in drafts:
        if d.table_id is None:
            takeaway.append({"id": d.id, "version": d.version, "items": len(d.items), "staff": d.staff_name})
        else:
            by_table.setdefault(d.table_id, []).append(d)
    return {"branchId": ctx.branch_id,
            "areas": [{"id": a.id, "name": a.name, "active": a.active} for a in areas],
            "tables": [table_out(t, by_table.get(t.id, [])) for t in tables],
            "takeaway": takeaway}


@router.post("/api/areas", status_code=201)
def add_area(body: AreaIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    area = DiningArea(company_id=ctx.cid, branch_id=ctx.branch_id, name=body.name.strip(), active=body.active)
    ctx.db.add(area)
    save(ctx, area, "area.create", {"name": area.name, "branchId": ctx.branch_id})
    return {"id": area.id, "name": area.name, "active": area.active}


@router.post("/api/tables", status_code=201)
def add_table(body: TableIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    area = ctx.db.get(DiningArea, body.areaId)
    if area is None or area.company_id != ctx.cid or area.branch_id != ctx.branch_id:
        raise HTTPException(404, "Zal topilmadi")
    table = DiningTable(company_id=ctx.cid, branch_id=ctx.branch_id, area_id=area.id, name=body.name.strip(),
                        seats=body.seats, active=body.active)
    ctx.db.add(table)
    save(ctx, table, "table.create", {"name": table.name, "branchId": ctx.branch_id})
    return table_out(table, [])


@router.put("/api/tables/{table_id}")
def edit_table(table_id: int, body: TableIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    table = branch_table(ctx, table_id)
    area = ctx.db.get(DiningArea, body.areaId)
    if area is None or area.company_id != ctx.cid or area.branch_id != ctx.branch_id:
        raise HTTPException(404, "Zal topilmadi")
    occupied = ctx.db.scalars(select(DraftOrder).where(DraftOrder.company_id == ctx.cid,
                                                       DraftOrder.table_id == table.id)).all()
    if not body.active and occupied:
        raise HTTPException(409, "Band stolni o‘chirib bo‘lmaydi")
    table.area_id, table.name, table.seats, table.active = area.id, body.name.strip(), body.seats, body.active
    save(ctx, table, "table.update", {"name": table.name, "active": table.active})
    return table_out(table, occupied)


def locked_draft(ctx: Ctx, draft_id: int, version: int) -> DraftOrder:
    draft = ctx.db.scalar(select(DraftOrder).where(
        DraftOrder.id == draft_id, DraftOrder.company_id == ctx.cid,
        DraftOrder.branch_id == ctx.branch_id).with_for_update())
    if draft is None:
        raise HTTPException(404, "Draft not found")
    if draft.version != version:
        raise HTTPException(409, "Draft changed on another device")
    return draft


def validate_table(ctx: Ctx, table_id: int | None, service: str) -> DiningTable | None:
    if service == "takeaway":
        if table_id is not None:
            raise HTTPException(422, "Olib ketish buyurtmasiga stol biriktirilmaydi")
        return None
    if table_id is None:
        raise HTTPException(422, "Zalda xizmat uchun stol tanlang")
    table = branch_table(ctx, table_id)
    if not table.active:
        raise HTTPException(409, "Stol faol emas")
    return table


@router.post("/api/drafts/{draft_id}/move")
def move_draft(draft_id: int, body: MoveIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    draft = locked_draft(ctx, draft_id, body.version)
    table = validate_table(ctx, body.tableId, body.service)
    if table is not None:
        taken = ctx.db.scalar(select(DraftOrder.id).where(
            DraftOrder.company_id == ctx.cid, DraftOrder.table_id == table.id, DraftOrder.id != draft.id))
        if taken is not None:
            raise HTTPException(409, "Stol band; birlashtirish uchun menejer kerak")
    before = {"id": draft.table_id}
    draft.table_id, draft.service = (table.id if table else None), body.service
    draft.version += 1
    draft.updated_at = now_ms()
    audit_record(ctx, "draft.move", draft.id, before, {"id": draft.table_id, "version": draft.version})
    ctx.db.commit()
    return {"id": draft.id, "tableId": draft.table_id, "service": draft.service, "version": draft.version}


@router.post("/api/drafts/{draft_id}/merge")
def merge_drafts(draft_id: int, body: MergeIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    if draft_id == body.targetId:
        raise HTTPException(422, "Draftni o‘ziga birlashtirib bo‘lmaydi")
    first, second = sorted([(draft_id, body.version), (body.targetId, body.targetVersion)])
    locked = {first[0]: locked_draft(ctx, *first), second[0]: locked_draft(ctx, *second)}
    source, target = locked[draft_id], locked[body.targetId]
    if len(source.items) + len(target.items) > 50:
        raise HTTPException(422, "Buyurtmada pozitsiyalar ko‘p")
    target.items = [*target.items, *source.items]
    target.version += 1
    target.updated_at = now_ms()
    audit_record(ctx, "draft.merge", target.id, {"id": source.id}, {"id": target.id, "version": target.version})
    ctx.db.delete(source)
    ctx.db.commit()
    return {"id": target.id, "tableId": target.table_id, "items": target.items, "version": target.version}


class LayoutIn(BaseModel):
    x: int = Field(ge=0, le=940)
    y: int = Field(ge=0, le=540)
    width: int = Field(ge=60, le=400)
    height: int = Field(ge=60, le=500)
    shape: Literal["round", "rectangle", "bar", "vip"] = "round"
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def inside_canvas(self):
        if self.x + self.width > 1000 or self.y + self.height > 600:
            raise ValueError("Stol xarita chegarasidan chiqmasin")
        return self


@router.patch("/api/tables/{table_id}/layout")
def update_layout(table_id: int, body: LayoutIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    table = branch_table(ctx, table_id)
    layout = body.model_dump(exclude={"version"})
    result = ctx.db.execute(update(DiningTable).where(
        DiningTable.id == table.id, DiningTable.company_id == ctx.cid,
        DiningTable.branch_id == ctx.branch_id, DiningTable.layout_version == body.version
    ).values(layout=layout, layout_version=body.version + 1))
    if result.rowcount != 1:
        ctx.db.rollback()
        raise HTTPException(409, "Xarita boshqa qurilmada o‘zgargan. Yangilang")
    audit_record(ctx, "table.layout", table.id, {}, layout)
    ctx.db.commit()
    return {"layout": layout, "layoutVersion": body.version + 1}


class SplitIn(BaseModel):
    version: int = Field(ge=1)
    guest: int = Field(ge=1, le=50)


@router.post("/api/drafts/{draft_id}/split", status_code=201)
def split_draft(draft_id: int, body: SplitIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    draft = locked_draft(ctx, draft_id, body.version)
    selected = [i for i in draft.items if i.get("guest", 1) == body.guest]
    remaining = [i for i in draft.items if i.get("guest", 1) != body.guest]
    if not selected or not remaining:
        raise HTTPException(422, "Ajratish uchun kamida ikki mehmon buyurtmasi kerak")
    result = ctx.db.execute(update(DraftOrder).where(DraftOrder.id == draft.id, DraftOrder.version == body.version).values(items=remaining, version=body.version + 1, updated_at=now_ms()))
    if result.rowcount != 1:
        ctx.db.rollback()
        raise HTTPException(409, "Qoralama boshqa qurilmada o‘zgargan. Yangilab qayta tekshiring")
    import secrets
    other = DraftOrder(company_id=ctx.cid, branch_id=ctx.branch_id, client_key=secrets.token_hex(16), items=selected,
                       customer=draft.customer, note=draft.note, guest_count=draft.guest_count, waiter_name=draft.waiter_name,
                       table_id=draft.table_id, service=draft.service, staff_name=draft.staff_name)
    ctx.db.add(other)
    ctx.db.flush()
    audit_record(ctx, "draft.split", draft.id, {}, {"id": other.id, "version": body.version + 1})
    ctx.db.commit()
    return {"sourceId": draft.id, "id": other.id}


class ReassignIn(BaseModel):
    version: int = Field(ge=1)
    staffId: int


@router.post("/api/drafts/{draft_id}/assign")
def assign_draft(draft_id: int, body: ReassignIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    draft = locked_draft(ctx, draft_id, body.version)
    staff = ctx.db.get(Staff, body.staffId)
    if staff is None or staff.company_id != ctx.cid or not staff.active or (staff.branch_id is not None and staff.branch_id != ctx.branch_id):
        raise HTTPException(404, "Xodim topilmadi")
    result = ctx.db.execute(update(DraftOrder).where(DraftOrder.id == draft.id, DraftOrder.version == body.version).values(waiter_name=staff.name, version=body.version + 1, updated_at=now_ms()))
    if result.rowcount != 1:
        ctx.db.rollback()
        raise HTTPException(409, "Qoralama boshqa qurilmada o‘zgargan. Yangilab qayta tekshiring")
    audit_record(ctx, "draft.assign", draft.id, {}, {"id": staff.id})
    ctx.db.commit()
    return {"id": draft.id, "waiter": staff.name, "version": body.version + 1}
