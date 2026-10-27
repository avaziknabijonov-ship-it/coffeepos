"""Branch low-stock notifications, stock transfers and stocktake approval."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import stock as branch_stock
from .audit import record as audit_record
from .core import MANAGERS, Ctx, require, rows, start_of_day_ms
from .db import Branch, Ingredient, Inventory, StockMove, StockNotification, StockTransfer, now_ms

router = APIRouter()
EPS = 0.000001


def refresh_low_stock(db: Session, cid: int, branch_id: int) -> list[StockNotification]:
    """Open one notification per low-stock episode; resolve it once stock recovers."""
    levels = branch_stock.levels(db, cid, branch_id)
    open_rows = {n.ingredient: n for n in db.scalars(select(StockNotification).where(
        StockNotification.company_id == cid, StockNotification.branch_id == branch_id,
        StockNotification.resolved_at.is_(None)))}
    opened = []
    for key, level in levels.items():
        low = level["min"] > 0 and level["stock"] <= level["min"]
        current = open_rows.get(key)
        if low and current is None:
            row = StockNotification(company_id=cid, branch_id=branch_id, ingredient=key,
                                    open_key=f"{branch_id}:{key}", stock=level["stock"], min=level["min"])
            try:
                with db.begin_nested():
                    db.add(row)
            except IntegrityError:
                continue  # Opened concurrently by another request.
            opened.append(row)
        elif current is not None and not low:
            current.resolved_at, current.open_key = now_ms(), None
    return opened


def notification_out(n: StockNotification, names: dict) -> dict:
    ing = names.get(n.ingredient)
    return {"id": n.id, "branchId": n.branch_id, "ingredient": n.ingredient,
            "name": ing.name if ing else n.ingredient, "unit": ing.unit if ing else "",
            "stock": n.stock, "min": n.min, "openedAt": n.opened_at, "resolvedAt": n.resolved_at}


@router.get("/api/stock/notifications")
def stock_notifications(include_resolved: bool = False, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    refresh_low_stock(ctx.db, ctx.cid, ctx.branch_id)
    ctx.db.commit()
    q = select(StockNotification).where(StockNotification.company_id == ctx.cid,
                                        StockNotification.branch_id == ctx.branch_id)
    if not include_resolved:
        q = q.where(StockNotification.resolved_at.is_(None))
    names = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    items = ctx.db.scalars(q.order_by(StockNotification.id.desc()).limit(200)).all()
    return {"items": [notification_out(n, names) for n in items]}


class MinIn(BaseModel):
    min: float = Field(ge=0)


def own_branch(ctx: Ctx, branch_id: int) -> Branch:
    branch = ctx.db.get(Branch, branch_id)
    if branch is None or branch.company_id != ctx.cid:
        raise HTTPException(404, "Filial topilmadi")
    if ctx.staff.branch_id is not None and ctx.staff.branch_id != branch_id:
        raise HTTPException(403, "Bu filial uchun ruxsat yo'q")
    return branch


@router.put("/api/branches/{branch_id}/stock/{key}/min")
def set_branch_min(branch_id: int, key: str, body: MinIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    own_branch(ctx, branch_id)
    ing = ctx.db.scalar(select(Ingredient).where(Ingredient.company_id == ctx.cid, Ingredient.key == key))
    if ing is None:
        raise HTTPException(404, "Xomashyo topilmadi")
    branch_stock.set_min(ctx.db, ctx.cid, branch_id, ing, body.min)
    audit_record(ctx, "stock.min", ing.id, {}, {"ingredient": key, "branchId": branch_id, "stock": body.min})
    refresh_low_stock(ctx.db, ctx.cid, branch_id)
    ctx.db.commit()
    return {"branchId": branch_id, "ingredient": key, "min": body.min}


# ---------- transfers ----------
class TransferLineIn(BaseModel):
    ing: str = Field(min_length=1, max_length=64)
    qty: float = Field(gt=0)


class TransferIn(BaseModel):
    clientKey: str = Field(pattern=r"^[a-zA-Z0-9_-]{12,64}$")
    toBranchId: int
    lines: list[TransferLineIn] = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=200)


class ReceiveLineIn(BaseModel):
    ing: str
    qty: float = Field(ge=0)


class ReceiveIn(BaseModel):
    lines: list[ReceiveLineIn] | None = None


def transfer_out(t: StockTransfer) -> dict:
    return {"id": t.id, "clientKey": t.client_key, "fromBranchId": t.from_branch_id, "toBranchId": t.to_branch_id,
            "status": t.status, "lines": t.lines, "receivedLines": t.received_lines, "note": t.note,
            "dispatchedBy": t.dispatched_by, "dispatchedAt": t.dispatched_at,
            "closedBy": t.closed_by, "closedAt": t.closed_at}


def locked_ingredients(db: Session, cid: int) -> dict[str, Ingredient]:
    return {i.key: i for i in db.scalars(select(Ingredient).where(Ingredient.company_id == cid).with_for_update())}


@router.post("/api/transfers", status_code=201)
def dispatch_transfer(body: TransferIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    db, cid, source = ctx.db, ctx.cid, ctx.branch_id
    existing = db.scalar(select(StockTransfer).where(StockTransfer.company_id == cid,
                                                     StockTransfer.client_key == body.clientKey))
    if existing is not None:
        return transfer_out(existing)
    target = own_branch_any(ctx, body.toBranchId)
    if target.id == source:
        raise HTTPException(422, "Bir filialning o‘ziga ko‘chirib bo‘lmaydi")
    if not target.active:
        raise HTTPException(409, "Filial faol emas")
    keys = [line.ing for line in body.lines]
    if len(set(keys)) != len(keys):
        raise HTTPException(422, "Xomashyo takrorlangan")
    ingredients = locked_ingredients(db, cid)
    lines = []
    for line in body.lines:
        ing = ingredients.get(line.ing)
        if ing is None:
            raise HTTPException(404, f"Xomashyo topilmadi: {line.ing}")
        if branch_stock.get(db, cid, source, ing, lock=True) + EPS < line.qty:
            raise HTTPException(409, f"Omborda yetarli emas: {ing.name}")
        lines.append({"ing": ing.key, "name": ing.name, "unit": ing.unit, "qty": line.qty, "unitCost": ing.cost})
    transfer = StockTransfer(company_id=cid, client_key=body.clientKey, from_branch_id=source,
                             to_branch_id=target.id, lines=lines, note=body.note.strip(),
                             dispatched_by=ctx.staff.name)
    db.add(transfer)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ko‘chirish allaqachon yuborilgan; qayta tekshiring") from None
    for line in lines:
        branch_stock.adjust(db, cid, source, ingredients[line["ing"]], -line["qty"])
        db.add(StockMove(company_id=cid, branch_id=source, ingredient=line["ing"], qty=-line["qty"],
                         reason="transfer_out", note=str(transfer.id), staff_name=ctx.staff.name))
    audit_record(ctx, "transfer.dispatch", transfer.id, {}, {"branchId": target.id, "items": [
        {"key": line["ing"], "qty": line["qty"]} for line in lines]})
    refresh_low_stock(db, cid, source)
    db.commit()
    return transfer_out(transfer)


def own_branch_any(ctx: Ctx, branch_id: int) -> Branch:
    """Destination may be any branch of the company."""
    branch = ctx.db.get(Branch, branch_id)
    if branch is None or branch.company_id != ctx.cid:
        raise HTTPException(404, "Filial topilmadi")
    return branch


def locked_transfer(ctx: Ctx, transfer_id: int) -> StockTransfer:
    transfer = ctx.db.scalar(select(StockTransfer).where(
        StockTransfer.id == transfer_id, StockTransfer.company_id == ctx.cid).with_for_update())
    if transfer is None:
        raise HTTPException(404, "Ko‘chirish topilmadi")
    return transfer


@router.post("/api/transfers/{transfer_id}/receive")
def receive_transfer(transfer_id: int, body: ReceiveIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    db, cid = ctx.db, ctx.cid
    transfer = locked_transfer(ctx, transfer_id)
    if transfer.to_branch_id != ctx.branch_id:
        raise HTTPException(403, "Qabul qiluvchi filialda tasdiqlang")
    if transfer.status != "in_transit":
        raise HTTPException(409, "Ko‘chirish allaqachon yopilgan")
    sent = {line["ing"]: line for line in transfer.lines}
    received = {line.ing: line.qty for line in body.lines} if body.lines else {k: v["qty"] for k, v in sent.items()}
    if set(received) - set(sent):
        raise HTTPException(422, "Yuborilmagan xomashyo")
    ingredients = locked_ingredients(db, cid)
    out = []
    for key, line in sent.items():
        qty = received.get(key, 0.0)
        if qty > line["qty"] + EPS:
            raise HTTPException(422, "Qabul miqdori yuborilganidan oshmasin")
        out.append({"ing": key, "qty": qty, "loss": round(line["qty"] - qty, 6)})
        if qty > 0 and key in ingredients:
            branch_stock.adjust(db, cid, transfer.to_branch_id, ingredients[key], qty)
            db.add(StockMove(company_id=cid, branch_id=transfer.to_branch_id, ingredient=key, qty=qty,
                             reason="transfer_in", note=str(transfer.id), staff_name=ctx.staff.name))
    transfer.status, transfer.received_lines = "received", out
    transfer.closed_by, transfer.closed_at = ctx.staff.name, now_ms()
    audit_record(ctx, "transfer.receive", transfer.id, {"status": "in_transit"}, {"status": "received", "items": [
        {"key": line["ing"], "qty": line["qty"]} for line in out]})
    refresh_low_stock(db, cid, transfer.to_branch_id)
    db.commit()
    return transfer_out(transfer)


@router.post("/api/transfers/{transfer_id}/cancel")
def cancel_transfer(transfer_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    db, cid = ctx.db, ctx.cid
    transfer = locked_transfer(ctx, transfer_id)
    if transfer.from_branch_id != ctx.branch_id:
        raise HTTPException(403, "Yuboruvchi filialda bekor qiling")
    if transfer.status != "in_transit":
        raise HTTPException(409, "Ko‘chirish allaqachon yopilgan")
    ingredients = locked_ingredients(db, cid)
    for line in transfer.lines:
        if line["ing"] in ingredients:
            branch_stock.adjust(db, cid, transfer.from_branch_id, ingredients[line["ing"]], line["qty"])
            db.add(StockMove(company_id=cid, branch_id=transfer.from_branch_id, ingredient=line["ing"],
                             qty=line["qty"], reason="transfer_cancel", note=str(transfer.id),
                             staff_name=ctx.staff.name))
    transfer.status, transfer.closed_by, transfer.closed_at = "cancelled", ctx.staff.name, now_ms()
    audit_record(ctx, "transfer.cancel", transfer.id, {"status": "in_transit"}, {"status": "cancelled"})
    db.commit()
    return transfer_out(transfer)


@router.get("/api/transfers")
def list_transfers(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(StockTransfer).where(StockTransfer.company_id == ctx.cid, (
        (StockTransfer.from_branch_id == ctx.branch_id) | (StockTransfer.to_branch_id == ctx.branch_id)
    )).order_by(StockTransfer.id.desc()).limit(200)
    return [transfer_out(t) for t in ctx.db.scalars(q)]


# ---------- stocktake approval ----------
def apply_count(ctx: Ctx, inv: Inventory) -> None:
    """Apply signed count differences (counted − expected at count time) to current stock."""
    ingredients = locked_ingredients(ctx.db, ctx.cid)
    for line in inv.lines:
        diff = line["diff"]
        if diff and line["ing"] in ingredients:
            branch_stock.adjust(ctx.db, ctx.cid, inv.branch_id, ingredients[line["ing"]], diff)
            ctx.db.add(StockMove(company_id=ctx.cid, branch_id=inv.branch_id, ingredient=line["ing"], qty=diff,
                                 reason="count", inventory_id=inv.id, staff_name=ctx.staff.name))


def pending_inventory(ctx: Ctx, inventory_id: int) -> Inventory:
    inv = ctx.db.scalar(select(Inventory).where(Inventory.id == inventory_id, Inventory.company_id == ctx.cid)
                        .with_for_update())
    if inv is None or (ctx.staff.branch_id is not None and inv.branch_id != ctx.staff.branch_id):
        raise HTTPException(404, "Inventarizatsiya topilmadi")
    if inv.status != "pending":
        raise HTTPException(409, "Inventarizatsiya allaqachon ko‘rib chiqilgan")
    return inv


@router.post("/api/inventories/{inventory_id}/approve")
def approve_inventory(inventory_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    inv = pending_inventory(ctx, inventory_id)
    if ctx.staff.role != "owner" and inv.staff_id == ctx.staff.id:
        raise HTTPException(403, "O‘zingiz sanagan inventarizatsiyani boshqa menejer tasdiqlasin")
    apply_count(ctx, inv)
    inv.status, inv.approved_by, inv.approved_at = "approved", ctx.staff.name, now_ms()
    audit_record(ctx, "inventory.approve", inv.id, {"status": "pending"},
                 {"status": "approved", "shortage": inv.shortage, "surplus": inv.surplus})
    refresh_low_stock(ctx.db, ctx.cid, inv.branch_id)
    ctx.db.commit()
    return {"id": inv.id, "status": inv.status, "approvedBy": inv.approved_by}


@router.post("/api/inventories/{inventory_id}/reject")
def reject_inventory(inventory_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    inv = pending_inventory(ctx, inventory_id)
    inv.status, inv.approved_by, inv.approved_at = "rejected", ctx.staff.name, now_ms()
    audit_record(ctx, "inventory.reject", inv.id, {"status": "pending"}, {"status": "rejected"})
    ctx.db.commit()
    return {"id": inv.id, "status": inv.status}


@router.get("/api/reports/inventory-variance")
def inventory_variance_report(days: int = 30, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    days = max(1, min(days, 366))
    q = select(Inventory).where(Inventory.company_id == ctx.cid, Inventory.branch_id == ctx.branch_id,
                                Inventory.status == "approved", Inventory.created_at >= start_of_day_ms(days - 1))
    by_ing: dict[str, dict] = {}
    for inv in ctx.db.scalars(q):
        for line in inv.lines:
            row = by_ing.setdefault(line["ing"], {"ingredient": line["ing"], "name": line["name"], "unit": line["unit"],
                                                  "counts": 0, "diff": 0.0, "value": 0})
            row["counts"] += 1
            row["diff"] = round(row["diff"] + line["diff"], 6)
            row["value"] += line["value"]
    items = sorted(by_ing.values(), key=lambda r: r["value"])
    return {"days": days, "branchId": ctx.branch_id, "items": items,
            "shortage": sum(-r["value"] for r in items if r["value"] < 0),
            "surplus": sum(r["value"] for r in items if r["value"] > 0)}
