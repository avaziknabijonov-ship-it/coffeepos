import os
import re
import secrets
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from . import seed
from .platform import router as platform_router, page_router as platform_page_router
from .db import (
    Base, Category, Company, Debt, DebtPayment, Expense, Ingredient, Inventory, Modifier, Order, Product, SalaryEntry, SessionLocal, Shift, Staff, StockMove, Subscription, engine, now_ms,
)
from .logic import build_item
from .security import LoginLimiter, check_pin, hash_pin, make_token, read_token

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Tashkent"))
Role = Literal["owner", "admin", "kassir", "barista"]
MANAGERS = ("owner", "admin")
CASHIERS = ("owner", "admin", "kassir")



def migrate() -> None:
    """Add columns introduced after a table was first created (no Alembic yet)."""
    have = {c["name"] for c in inspect(engine).get_columns("stock_moves")}
    with engine.begin() as conn:
        if "note" not in have:
            conn.execute(text("ALTER TABLE stock_moves ADD COLUMN note VARCHAR(32)"))
        if "inventory_id" not in have:
            conn.execute(text("ALTER TABLE stock_moves ADD COLUMN inventory_id INTEGER"))
        staff_cols = {c["name"] for c in inspect(engine).get_columns("staff")}
        product_cols = {c["name"] for c in inspect(engine).get_columns("products")}
        if "salary_type" not in staff_cols:
            conn.execute(text("ALTER TABLE staff ADD COLUMN salary_type VARCHAR(16) DEFAULT 'monthly'"))
        if "salary_rate" not in staff_cols:
            conn.execute(text("ALTER TABLE staff ADD COLUMN salary_rate BIGINT DEFAULT 0"))
        if "image_url" not in product_cols:
            conn.execute(text("ALTER TABLE products ADD COLUMN image_url TEXT"))
        payment_cols = {c["name"] for c in inspect(engine).get_columns("debt_payments")}
        if "shift_id" not in payment_cols:
            conn.execute(text("ALTER TABLE debt_payments ADD COLUMN shift_id INTEGER"))
    # Assign old repayments to a shift only when their timestamp matches exactly one shift.
    with SessionLocal() as db:
        old_payments = db.scalars(select(DebtPayment).where(DebtPayment.shift_id.is_(None))).all()
        for payment in old_payments:
            candidates = db.scalars(select(Shift).where(
                Shift.company_id == payment.company_id,
                Shift.opened_at <= payment.created_at,
                (Shift.closed_at.is_(None) | (Shift.closed_at >= payment.created_at)),
            )).all()
            if len(candidates) == 1:
                payment.shift_id = candidates[0].id
        db.commit()


def init_db() -> None:
    Base.metadata.create_all(engine)
    migrate()
    if os.environ.get("SEED_DEMO", "1") != "1":
        return
    with SessionLocal() as db:
        if db.scalar(select(Company).where(Company.slug == "demo")):
            return
        company = create_company(db, "demo", "Demo Coffee", "Rahbar", "1111")
        db.add(Staff(company_id=company.id, name="Dilnoza", role="kassir", pin_hash=hash_pin("2222")))
        db.add(Staff(company_id=company.id, name="Aziz", role="barista", pin_hash=hash_pin("3333")))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="CoffeePOS API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
limiter = LoginLimiter()
app.include_router(platform_router)
app.include_router(platform_page_router)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Ctx:
    def __init__(self, db: Session, staff: Staff, company: Company):
        self.db, self.staff, self.company = db, staff, company

    @property
    def cid(self) -> int:
        return self.company.id


def auth(db: Session = Depends(get_db), authorization: str = Header(default="")) -> Ctx:
    claims = read_token(db, authorization.removeprefix("Bearer ").strip()) if authorization else None
    if not claims:
        raise HTTPException(401, "Qaytadan kiring")
    staff = db.get(Staff, int(claims["sub"]))
    if not staff or not staff.active or staff.company_id != claims["cid"]:
        raise HTTPException(401, "Qaytadan kiring")
    return Ctx(db, staff, db.get(Company, staff.company_id))


def require(*roles: str):
    def dep(ctx: Ctx = Depends(auth)) -> Ctx:
        if ctx.staff.role not in roles:
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
        return ctx

    return dep


# ---------- serializers ----------

def staff_out(s: Staff) -> dict:
    return {"id": s.id, "name": s.name, "role": s.role, "active": s.active, "salaryType": s.salary_type or "monthly", "salaryRate": s.salary_rate or 0}


def order_out(o: Order) -> dict:
    return {
        "id": str(o.id), "number": o.number, "customer": o.customer, "items": o.items,
        "subtotal": o.subtotal, "discount": o.discount, "total": o.total, "cost": o.cost,
        "payment": o.payment, "cashGiven": o.cash_given, "status": o.status,
        "createdAt": o.created_at, "readyAt": o.ready_at, "barista": o.staff_name,
    }


def ingredient_out(i: Ingredient) -> dict:
    return {"id": i.key, "name": i.name, "unit": i.unit, "cost": i.cost, "stock": i.stock, "min": i.min}


def product_out(p: Product) -> dict:
    return {"id": p.key, "cat": p.cat, "name": p.name, "mods": p.mods, "sizes": p.sizes, "active": p.active, "imageUrl": p.image_url}


def shift_out(s: Shift | None) -> dict | None:
    if not s:
        return None
    return {
        "id": s.id, "staff": s.staff_name, "openedAt": s.opened_at, "openingCash": s.opening_cash,
        "closedAt": s.closed_at, "closingCash": s.closing_cash, "expectedCash": s.expected_cash,
    }


# ---------- helpers ----------

def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return f"{base or 'item'}-{secrets.token_hex(2)}"


def rows(db: Session, model, cid: int):
    return db.scalars(select(model).where(model.company_id == cid).order_by(model.id)).all()


def get_row(db: Session, model, cid: int, key: str):
    row = db.scalar(select(model).where(model.company_id == cid, model.key == key))
    if not row:
        raise HTTPException(404, "Topilmadi")
    return row


def open_shift(db: Session, cid: int) -> Shift | None:
    return db.scalar(select(Shift).where(Shift.company_id == cid, Shift.closed_at.is_(None)))


def start_of_day_ms(days_ago: int = 0) -> int:
    d = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return int(d.timestamp() * 1000)


def pin_taken(db: Session, cid: int, pin: str, exclude: int | None = None) -> bool:
    for s in rows(db, Staff, cid):
        if s.id != exclude and s.active and check_pin(pin, s.pin_hash):
            return True
    return False


def create_company(db: Session, slug: str, name: str, owner_name: str, owner_pin: str) -> Company:
    company = Company(slug=slug, name=name)
    db.add(company)
    db.flush()
    cid = company.id
    db.add(Staff(company_id=cid, name=owner_name, role="owner", pin_hash=hash_pin(owner_pin)))
    db.add(Subscription(company_id=cid, status="trial", trial_ends_at=now_ms() + 14 * 24 * 60 * 60 * 1000))
    for i, (key, cname) in enumerate(seed.CATEGORIES):
        db.add(Category(company_id=cid, key=key, name=cname, sort=i))
    for key, iname, unit, cost, stock, mn in seed.INGREDIENTS:
        db.add(Ingredient(company_id=cid, key=key, name=iname, unit=unit, cost=cost, stock=stock, min=mn))
    for i, (key, cat, pname, mods, sizes) in enumerate(seed.PRODUCTS):
        db.add(Product(company_id=cid, key=key, cat=cat, name=pname, mods=mods, sizes=sizes, sort=i))
    for i, (key, group, mname, price, effect) in enumerate(seed.MODIFIERS):
        db.add(Modifier(company_id=cid, key=key, group=group, name=mname, price=price, effect=effect, sort=i))
    return company


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


# ---------- auth ----------

PIN_RE = r"^\d{4,6}$"


class LoginIn(BaseModel):
    company: str = Field(min_length=1, max_length=64)
    pin: str = Field(pattern=PIN_RE)


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> dict:
    slug = body.company.strip().lower()
    key = f"{slug}|{request.client.host if request.client else '-'}"
    if limiter.blocked(key):
        raise HTTPException(429, "Ko'p urinish. 5 daqiqadan keyin qayta urining")
    company = db.scalar(select(Company).where(Company.slug == slug))
    staff = None
    if company:
        staff = next((s for s in rows(db, Staff, company.id) if s.active and check_pin(body.pin, s.pin_hash)), None)
    if not staff:
        limiter.fail(key)
        raise HTTPException(401, "Kofe bar yoki PIN noto'g'ri")
    limiter.reset(key)
    return {
        "token": make_token(db, staff.id, company.id),
        "staff": staff_out(staff),
        "company": {"slug": company.slug, "name": company.name},
    }


class RegisterIn(BaseModel):
    companyName: str = Field(min_length=2, max_length=128)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,40}$")
    ownerName: str = Field(min_length=2, max_length=64)
    ownerPin: str = Field(pattern=PIN_RE)


@app.post("/api/auth/register")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(Company).where(Company.slug == body.slug)):
        raise HTTPException(409, "Bu login band, boshqasini tanlang")
    create_company(db, body.slug, body.companyName.strip(), body.ownerName.strip(), body.ownerPin)
    db.commit()
    return login(LoginIn(company=body.slug, pin=body.ownerPin), request, db)


@app.get("/api/license/status")
def license_status(ctx: Ctx = Depends(auth)) -> dict:
    """Read-only subscription status. Does not block sales or verify payments."""
    sub = ctx.db.scalar(select(Subscription).where(Subscription.company_id == ctx.cid))
    if sub is None:
        return {
            "status": "unconfigured",
            "trialEndsAt": None,
            "currentPeriodEndsAt": None,
            "graceEndsAt": None,
            "serverTime": now_ms(),
        }
    now = now_ms()
    status = sub.status
    if status == "trial" and sub.trial_ends_at is not None and now >= sub.trial_ends_at:
        status = "expired"
    elif status == "active" and sub.current_period_ends_at is not None and now >= sub.current_period_ends_at:
        status = "grace" if sub.grace_ends_at is not None and now < sub.grace_ends_at else "expired"
    elif status == "grace" and sub.grace_ends_at is not None and now >= sub.grace_ends_at:
        status = "expired"
    return {
        "status": status,
        "trialEndsAt": sub.trial_ends_at,
        "currentPeriodEndsAt": sub.current_period_ends_at,
        "graceEndsAt": sub.grace_ends_at,
        "serverTime": now,
    }


@app.get("/api/me")
def me(ctx: Ctx = Depends(auth)) -> dict:
    return {"staff": staff_out(ctx.staff), "company": {"slug": ctx.company.slug, "name": ctx.company.name}}


# ---------- menu ----------

@app.get("/api/menu")
def menu(ctx: Ctx = Depends(auth)) -> dict:
    db, cid = ctx.db, ctx.cid
    cats = sorted(rows(db, Category, cid), key=lambda c: (c.sort, c.id))
    prods = sorted(rows(db, Product, cid), key=lambda p: (p.sort, p.id))
    mods = sorted(rows(db, Modifier, cid), key=lambda m: (m.sort, m.id))
    return {
        "categories": [{"id": c.key, "name": c.name} for c in cats],
        "products": [product_out(p) for p in prods],
        "modifiers": [{"id": m.key, "group": m.group, "name": m.name, "price": m.price, "effect": m.effect} for m in mods],
        "ingredients": [ingredient_out(i) for i in rows(db, Ingredient, cid)],
    }


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


@app.post("/api/categories")
def add_category(body: CategoryIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    sort = len(rows(ctx.db, Category, ctx.cid))
    cat = Category(company_id=ctx.cid, key=slugify(body.name), name=body.name.strip(), sort=sort)
    ctx.db.add(cat)
    ctx.db.commit()
    return {"id": cat.key, "name": cat.name}


class CategoryEditIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


@app.patch("/api/categories/{key}")
def rename_category(key: str, body: CategoryEditIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    cat = get_row(ctx.db, Category, ctx.cid, key)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Kategoriya nomini kiriting")
    cat.name = name
    ctx.db.commit()
    return {"id": cat.key, "name": cat.name}


class CategoryOrderIn(BaseModel):
    keys: list[str] = Field(min_length=1)


@app.put("/api/categories/order")
def reorder_categories(body: CategoryOrderIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    cats = rows(ctx.db, Category, ctx.cid)
    actual = {c.key for c in cats}
    if len(body.keys) != len(actual) or set(body.keys) != actual:
        raise HTTPException(422, "Kategoriya ro'yxati mos kelmadi")
    for i, key in enumerate(body.keys):
        next(c for c in cats if c.key == key).sort = i
    ctx.db.commit()
    return {"ok": True}


@app.delete("/api/categories/{key}")
def delete_category(key: str, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    cat = get_row(ctx.db, Category, ctx.cid, key)
    if any(p.cat == key for p in rows(ctx.db, Product, ctx.cid)):
        raise HTTPException(400, "Kategoriyada mahsulotlar bor")
    ctx.db.delete(cat)
    ctx.db.commit()
    return {"ok": True}


class RecipeLineIn(BaseModel):
    ing: str
    qty: float = Field(gt=0)


class SizeIn(BaseModel):
    code: str = Field(min_length=1, max_length=8)
    label: str = Field(default="", max_length=8)
    volume: str | None = Field(default=None, max_length=16)
    price: int = Field(ge=0)
    recipe: list[RecipeLineIn] = []


class ProductIn(BaseModel):
    cat: str
    name: str = Field(min_length=1, max_length=128)
    mods: list[Literal["milk", "syrup", "shot"]] = []
    sizes: list[SizeIn] = Field(min_length=1)
    active: bool = True
    imageUrl: str | None = Field(default=None, max_length=500000)


def validate_product(ctx: Ctx, body: ProductIn) -> None:
    get_row(ctx.db, Category, ctx.cid, body.cat)
    ing_keys = {i.key for i in rows(ctx.db, Ingredient, ctx.cid)}
    codes = [s.code for s in body.sizes]
    if len(set(codes)) != len(codes):
        raise HTTPException(400, "O'lchamlar takrorlanmasin")
    for s in body.sizes:
        for line in s.recipe:
            if line.ing not in ing_keys:
                raise HTTPException(400, "Texkartada noma'lum xomashyo")


@app.post("/api/products")
def add_product(body: ProductIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    validate_product(ctx, body)
    p = Product(
        company_id=ctx.cid, key=slugify(body.name), cat=body.cat, name=body.name.strip(), mods=body.mods,
        sizes=[s.model_dump() for s in body.sizes], active=body.active, image_url=body.imageUrl, sort=len(rows(ctx.db, Product, ctx.cid)),
    )
    ctx.db.add(p)
    ctx.db.commit()
    return product_out(p)


@app.put("/api/products/{key}")
def update_product(key: str, body: ProductIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    p = get_row(ctx.db, Product, ctx.cid, key)
    validate_product(ctx, body)
    p.cat, p.name, p.mods = body.cat, body.name.strip(), body.mods
    p.sizes, p.active, p.image_url = [s.model_dump() for s in body.sizes], body.active, body.imageUrl
    ctx.db.commit()
    return product_out(p)


class ActiveIn(BaseModel):
    active: bool


@app.patch("/api/products/{key}/active")
def set_product_active(key: str, body: ActiveIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    p = get_row(ctx.db, Product, ctx.cid, key)
    p.active = body.active
    ctx.db.commit()
    return product_out(p)


@app.delete("/api/products/{key}")
def delete_product(key: str, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    ctx.db.delete(get_row(ctx.db, Product, ctx.cid, key))
    ctx.db.commit()
    return {"ok": True}


class ModifierIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    price: int = Field(ge=0)


@app.put("/api/modifiers/{key}")
def update_modifier(key: str, body: ModifierIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    m = get_row(ctx.db, Modifier, ctx.cid, key)
    m.name, m.price = body.name.strip(), body.price
    ctx.db.commit()
    return {"id": m.key, "group": m.group, "name": m.name, "price": m.price, "effect": m.effect}


class IngredientIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    unit: Literal["g", "ml", "dona"]
    cost: float = Field(ge=0)
    min: float = Field(ge=0)


@app.post("/api/ingredients")
def add_ingredient(body: IngredientIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    i = Ingredient(company_id=ctx.cid, key=slugify(body.name), stock=0, **body.model_dump())
    ctx.db.add(i)
    ctx.db.commit()
    return ingredient_out(i)


@app.put("/api/ingredients/{key}")
def update_ingredient(key: str, body: IngredientIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    i = get_row(ctx.db, Ingredient, ctx.cid, key)
    for k, v in body.model_dump().items():
        setattr(i, k, v)
    ctx.db.commit()
    return ingredient_out(i)


WRITEOFF_NOTES = ("spill", "expired", "staff", "broken", "other")


class StockIn(BaseModel):
    ing: str
    qty: float
    reason: Literal["intake", "writeoff", "count"]
    note: Literal[WRITEOFF_NOTES] | None = None


@app.post("/api/stock")
def stock_move(body: StockIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    i = get_row(ctx.db, Ingredient, ctx.cid, body.ing)
    if body.reason == "count":
        if body.qty < 0:
            raise HTTPException(400, "Qoldiq manfiy bo'lmaydi")
        delta = body.qty - i.stock
    elif body.qty <= 0:
        raise HTTPException(400, "Miqdor musbat bo'lsin")
    else:
        delta = body.qty if body.reason == "intake" else -body.qty
    note = (body.note or "other") if body.reason == "writeoff" else None
    i.stock += delta
    ctx.db.add(StockMove(company_id=ctx.cid, ingredient=i.key, qty=delta, reason=body.reason, note=note, staff_name=ctx.staff.name))
    ctx.db.commit()
    return ingredient_out(i)


class CountLine(BaseModel):
    ing: str
    counted: float = Field(ge=0)


class InventoryIn(BaseModel):
    lines: list[CountLine] = Field(min_length=1)
    note: str = Field("", max_length=200)


def inventory_out(inv: Inventory) -> dict:
    return {
        "id": inv.id, "staff": inv.staff_name, "note": inv.note, "lines": inv.lines,
        "shortage": inv.shortage, "surplus": inv.surplus, "createdAt": inv.created_at,
    }


@app.post("/api/inventories")
def create_inventory(body: InventoryIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    keys = [line.ing for line in body.lines]
    if len(set(keys)) != len(keys):
        raise HTTPException(400, "Xomashyo takrorlangan")
    ings = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    inv = Inventory(company_id=ctx.cid, staff_name=ctx.staff.name, note=body.note.strip(), lines=[])
    ctx.db.add(inv)
    ctx.db.flush()
    lines, shortage, surplus = [], 0, 0
    for line in body.lines:
        i = ings.get(line.ing)
        if not i:
            raise HTTPException(404, f"Xomashyo topilmadi: {line.ing}")
        diff = line.counted - i.stock
        value = round(diff * i.cost)
        if value < 0:
            shortage += -value
        else:
            surplus += value
        lines.append({"ing": i.key, "name": i.name, "unit": i.unit, "expected": i.stock, "counted": line.counted, "diff": diff, "value": value})
        if diff:
            ctx.db.add(StockMove(company_id=ctx.cid, ingredient=i.key, qty=diff, reason="count", inventory_id=inv.id, staff_name=ctx.staff.name))
        i.stock = line.counted
    inv.lines, inv.shortage, inv.surplus = lines, shortage, surplus
    ctx.db.commit()
    return inventory_out(inv)


@app.get("/api/inventories")
def list_inventories(days: int = 90, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = (
        select(Inventory)
        .where(Inventory.company_id == ctx.cid, Inventory.created_at >= start_of_day_ms(days))
        .order_by(Inventory.id.desc())
        .limit(100)
    )
    return [inventory_out(inv) for inv in ctx.db.scalars(q)]


@app.get("/api/reports/losses")
def losses_report(days: int = 30, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Write-offs by cause and ingredient, plus stocktake shortage/surplus, valued at current cost."""
    since = start_of_day_ms(days)
    ings = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    moves = ctx.db.scalars(
        select(StockMove).where(
            StockMove.company_id == ctx.cid, StockMove.reason.in_(("writeoff", "count")), StockMove.created_at >= since
        )
    )
    by_note: dict[str, int] = {}
    by_ing: dict[str, dict] = {}
    for m in moves:
        i = ings.get(m.ingredient)
        value = round(m.qty * (i.cost if i else 0))
        row = by_ing.setdefault(m.ingredient, {
            "ing": m.ingredient, "name": i.name if i else m.ingredient, "unit": i.unit if i else "",
            "writeoffQty": 0.0, "writeoffValue": 0, "countQty": 0.0, "countValue": 0,
        })
        if m.reason == "writeoff":
            by_note[m.note or "other"] = by_note.get(m.note or "other", 0) - value
            row["writeoffQty"] -= m.qty
            row["writeoffValue"] -= value
        else:
            row["countQty"] += m.qty
            row["countValue"] += value
    invs = ctx.db.scalars(select(Inventory).where(Inventory.company_id == ctx.cid, Inventory.created_at >= since)).all()
    items = sorted(by_ing.values(), key=lambda r: r["writeoffValue"] - r["countValue"], reverse=True)
    return {
        "days": days,
        "writeoffTotal": sum(by_note.values()),
        "byNote": by_note,
        "inventories": len(invs),
        "shortage": sum(x.shortage for x in invs),
        "surplus": sum(x.surplus for x in invs),
        "items": items,
    }


@app.get("/api/stock/moves")
def stock_moves(days: int = 7, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = (
        select(StockMove)
        .where(StockMove.company_id == ctx.cid, StockMove.reason != "sale", StockMove.created_at >= start_of_day_ms(days))
        .order_by(StockMove.id.desc())
        .limit(200)
    )
    return [
        {
            "id": m.id, "ing": m.ingredient, "qty": m.qty, "reason": m.reason, "note": m.note,
            "inventoryId": m.inventory_id, "staff": m.staff_name, "createdAt": m.created_at,
        }
        for m in ctx.db.scalars(q)
    ]


# ---------- staff ----------

class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    role: Role
    pin: str | None = Field(default=None, pattern=PIN_RE)
    active: bool = True
    salaryType: Literal["monthly", "daily"] = "monthly"
    salaryRate: int = Field(default=0, ge=0)


def guard_owner(ctx: Ctx, role: str) -> None:
    if role == "owner" and ctx.staff.role != "owner":
        raise HTTPException(403, "Faqat rahbar rahbar qo'sha oladi")


@app.get("/api/staff")
def list_staff(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    return [staff_out(s) for s in rows(ctx.db, Staff, ctx.cid)]


@app.get("/api/staff/expense-recipients")
def expense_recipients(ctx: Ctx = Depends(require(*CASHIERS))) -> list[dict]:
    return [{"id": staff.id, "name": staff.name} for staff in rows(ctx.db, Staff, ctx.cid) if staff.active]


@app.post("/api/staff")
def add_staff(body: StaffIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    guard_owner(ctx, body.role)
    if not body.pin:
        raise HTTPException(400, "PIN kerak")
    if pin_taken(ctx.db, ctx.cid, body.pin):
        raise HTTPException(409, "Bu PIN band")
    s = Staff(company_id=ctx.cid, name=body.name.strip(), role=body.role, pin_hash=hash_pin(body.pin), active=body.active, salary_type=body.salaryType, salary_rate=body.salaryRate)
    ctx.db.add(s)
    ctx.db.commit()
    return staff_out(s)


@app.put("/api/staff/{sid}")
def update_staff(sid: int, body: StaffIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    s = ctx.db.get(Staff, sid)
    if not s or s.company_id != ctx.cid:
        raise HTTPException(404, "Topilmadi")
    guard_owner(ctx, s.role)
    guard_owner(ctx, body.role)
    if s.id == ctx.staff.id and (body.role != s.role or not body.active):
        raise HTTPException(400, "O'zingizning rolingizni o'zgartira olmaysiz")
    if body.pin:
        if pin_taken(ctx.db, ctx.cid, body.pin, exclude=s.id):
            raise HTTPException(409, "Bu PIN band")
        s.pin_hash = hash_pin(body.pin)
    s.name, s.role, s.active = body.name.strip(), body.role, body.active
    s.salary_type, s.salary_rate = body.salaryType, body.salaryRate
    ctx.db.commit()
    return staff_out(s)


# ---------- shifts ----------

class OpenShiftIn(BaseModel):
    openingCash: int = Field(ge=0)


class CloseShiftIn(BaseModel):
    closingCash: int = Field(ge=0)


def shift_summary(db: Session, shift: Shift) -> dict:
    orders = db.scalars(select(Order).where(Order.shift_id == shift.id)).all()
    by_payment: dict[str, int] = {}
    for o in orders:
        by_payment[o.payment] = by_payment.get(o.payment, 0) + o.total
    repayments = db.scalars(select(DebtPayment).where(DebtPayment.shift_id == shift.id)).all()
    repaid_by_method: dict[str, int] = {}
    for p in repayments:
        repaid_by_method[p.method] = repaid_by_method.get(p.method, 0) + p.amount
    expenses = db.scalars(select(Expense).where(Expense.shift_id == shift.id)).all()
    cash_expenses = sum(e.amount for e in expenses if e.method == "naqd")
    return {
        "shift": shift_out(shift),
        "expenses": sum(e.amount for e in expenses),
        "cashExpenses": cash_expenses,
        "debtRepayments": sum(p.amount for p in repayments),
        "debtRepaymentsByMethod": repaid_by_method,
        "orders": len(orders),
        "revenue": sum(o.total for o in orders),
        "byPayment": by_payment,
        "expectedCash": shift.opening_cash + by_payment.get("naqd", 0) + repaid_by_method.get("naqd", 0) - cash_expenses,
    }


@app.post("/api/shifts/open")
def shift_open(body: OpenShiftIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    if open_shift(ctx.db, ctx.cid):
        raise HTTPException(409, "Smena allaqachon ochiq")
    s = Shift(company_id=ctx.cid, staff_name=ctx.staff.name, opening_cash=body.openingCash)
    ctx.db.add(s)
    ctx.db.commit()
    return shift_out(s)


@app.get("/api/shifts/current")
def shift_current(ctx: Ctx = Depends(auth)) -> dict | None:
    s = open_shift(ctx.db, ctx.cid)
    return shift_summary(ctx.db, s) if s else None


@app.post("/api/shifts/close")
def shift_close(body: CloseShiftIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    s = open_shift(ctx.db, ctx.cid)
    if not s:
        raise HTTPException(409, "Ochiq smena yo'q")
    summary = shift_summary(ctx.db, s)
    s.closed_at, s.closed_by = now_ms(), ctx.staff.name
    s.closing_cash, s.expected_cash = body.closingCash, summary["expectedCash"]
    ctx.db.commit()
    return {**summary, "shift": shift_out(s), "difference": body.closingCash - summary["expectedCash"]}


@app.get("/api/shifts/{shift_id}/report")
def shift_report(shift_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    shift = ctx.db.get(Shift, shift_id)
    if not shift or shift.company_id != ctx.cid:
        raise HTTPException(404, "Smena topilmadi")
    report = shift_summary(ctx.db, shift)
    expenses = ctx.db.scalars(select(Expense).where(Expense.company_id == ctx.cid, Expense.shift_id == shift_id).order_by(Expense.created_at)).all()
    payments = ctx.db.scalars(select(DebtPayment).where(DebtPayment.company_id == ctx.cid, DebtPayment.shift_id == shift_id).order_by(DebtPayment.created_at)).all()
    report["expenseDetails"] = [expense_out(e) for e in expenses]
    report["repaymentDetails"] = [{"amount": p.amount, "method": p.method, "note": p.note, "createdAt": p.created_at} for p in payments]
    report["difference"] = (shift.closing_cash - report["expectedCash"]) if shift.closed_at is not None and shift.closing_cash is not None else None
    return report


@app.get("/api/shifts")
def shift_history(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(Shift).where(Shift.company_id == ctx.cid).order_by(Shift.id.desc()).limit(30)
    return [shift_summary(ctx.db, s) for s in ctx.db.scalars(q)]


# ---------- orders ----------

class OrderItemIn(BaseModel):
    productId: str
    size: str
    modIds: list[str] = []
    qty: int = 1


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    customer: str = Field(default="", max_length=64)
    discountPct: int = Field(default=0, ge=0, le=100)
    payment: Literal["naqd", "karta", "payme", "click", "qarz"]
    debtPhone: str = Field(default="", max_length=32)
    debtNote: str = Field(default="", max_length=256)
    cashGiven: int | None = Field(default=None, ge=0)


@app.post("/api/orders")
def create_order(body: OrderIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    db, cid = ctx.db, ctx.cid
    shift = open_shift(db, cid)
    if not shift:
        raise HTTPException(409, "Avval smenani oching")
    if body.discountPct > 0 and body.discountPct not in (5, 10) and ctx.staff.role not in MANAGERS:
        raise HTTPException(403, "Bunday chegirma uchun ruxsat yo'q")
    prods = {p.key: p for p in rows(db, Product, cid)}
    mods = {m.key: m for m in rows(db, Modifier, cid)}
    ings = {i.key: i for i in rows(db, Ingredient, cid)}

    items: list[dict] = []
    for it in body.items:
        product = prods.get(it.productId)
        if not product:
            raise HTTPException(400, "Mahsulot topilmadi")
        built = build_item(product, it.size, it.modIds, it.qty, mods, ings)
        same = next((x for x in items if x["key"] == built["key"]), None)
        if same:
            same["qty"] += built["qty"]
        else:
            items.append(built)

    subtotal = sum(i["unitPrice"] * i["qty"] for i in items)
    discount = round(subtotal * body.discountPct / 100 / 100) * 100
    total = subtotal - discount
    if body.payment == "qarz" and not body.customer.strip():
        raise HTTPException(400, "Qarz uchun mijoz ismi kerak")
    if body.payment == "naqd" and body.cashGiven is not None and body.cashGiven < total:
        raise HTTPException(400, "Berilgan pul yetarli emas")

    day_orders = db.scalars(
        select(Order.number).where(Order.company_id == cid, Order.created_at >= start_of_day_ms())
    ).all()
    order = Order(
        company_id=cid, shift_id=shift.id, number=max(day_orders, default=0) + 1, customer=body.customer.strip(),
        items=items, subtotal=subtotal, discount=discount, total=total,
        cost=sum(i["unitCost"] * i["qty"] for i in items), payment=body.payment,
        cash_given=body.cashGiven if body.payment == "naqd" else None, staff_name=ctx.staff.name,
    )
    db.add(order)
    db.flush()
    if body.payment == "qarz":
        db.add(Debt(company_id=cid, order_id=order.id, customer=body.customer.strip(), phone=body.debtPhone.strip(), note=body.debtNote.strip(), total=total))
    used: dict[str, float] = {}
    for it in items:
        for line in it["consumption"]:
            used[line["ing"]] = used.get(line["ing"], 0) + line["qty"] * it["qty"]
    for key, qty in used.items():
        if key in ings:
            ings[key].stock -= qty
            db.add(StockMove(company_id=cid, ingredient=key, qty=-qty, reason="sale", order_id=order.id, staff_name=ctx.staff.name))
    db.commit()
    return order_out(order)


class StatusIn(BaseModel):
    status: Literal["new", "preparing", "ready", "done"]


@app.patch("/api/orders/{oid}")
def set_status(oid: int, body: StatusIn, ctx: Ctx = Depends(auth)) -> dict:
    o = ctx.db.get(Order, oid)
    if not o or o.company_id != ctx.cid:
        raise HTTPException(404, "Topilmadi")
    o.status = body.status
    if body.status == "ready":
        o.ready_at = now_ms()
    ctx.db.commit()
    return order_out(o)


@app.get("/api/sync")
def sync(since: int | None = None, ctx: Ctx = Depends(auth)) -> dict:
    """Polled by every screen: today's orders, stock levels and the open shift."""
    db, cid = ctx.db, ctx.cid
    since = since if since is not None else start_of_day_ms()
    q = select(Order).where(Order.company_id == cid, Order.created_at >= since).order_by(Order.id)
    shift = open_shift(db, cid)
    return {
        "orders": [order_out(o) for o in db.scalars(q)],
        "stock": {i.key: i.stock for i in rows(db, Ingredient, cid)},
        "shift": shift_summary(db, shift) if shift else None,
    }


@app.get("/api/reports/daily")
def daily_report(days: int = 7, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    days = max(1, min(days, 92))
    start = start_of_day_ms(days - 1)
    orders = ctx.db.scalars(select(Order).where(Order.company_id == ctx.cid, Order.created_at >= start)).all()
    out = []
    for d in range(days - 1, -1, -1):
        lo, hi = start_of_day_ms(d), start_of_day_ms(d - 1)
        day = [o for o in orders if lo <= o.created_at < hi]
        out.append({"day": lo, "revenue": sum(o.total for o in day), "cost": sum(o.cost for o in day), "orders": len(day)})
    return out


# ---------- salary and debts ----------

class SalaryConfigIn(BaseModel):
    salaryType: Literal["monthly", "daily"]
    salaryRate: int = Field(ge=0)


@app.patch("/api/staff/{sid}/salary")
def salary_config(sid: int, body: SalaryConfigIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    staff = ctx.db.get(Staff, sid)
    if not staff or staff.company_id != ctx.cid:
        raise HTTPException(404, "Xodim topilmadi")
    staff.salary_type, staff.salary_rate = body.salaryType, body.salaryRate
    ctx.db.commit()
    return staff_out(staff)


class SalaryEntryIn(BaseModel):
    staffId: int
    kind: Literal["day", "bonus", "deduction", "advance", "payment"]
    amount: int = Field(gt=0)
    note: str = Field(default="", max_length=256)


@app.post("/api/salary/entries")
def add_salary_entry(body: SalaryEntryIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    staff = ctx.db.get(Staff, body.staffId)
    if not staff or staff.company_id != ctx.cid:
        raise HTTPException(404, "Xodim topilmadi")
    row = SalaryEntry(company_id=ctx.cid, staff_id=staff.id, kind=body.kind, amount=body.amount, note=body.note)
    ctx.db.add(row)
    ctx.db.commit()
    return {"id": row.id}


@app.get("/api/salary")
def salary_report(month: str, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=TZ)
        end = (start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1))
    except ValueError:
        raise HTTPException(400, "Oy YYYY-MM formatida bo'lsin")
    entries = ctx.db.scalars(select(SalaryEntry).where(SalaryEntry.company_id == ctx.cid, SalaryEntry.created_at >= int(start.timestamp() * 1000), SalaryEntry.created_at < int(end.timestamp() * 1000))).all()
    result = []
    for staff in rows(ctx.db, Staff, ctx.cid):
        own = [e for e in entries if e.staff_id == staff.id]
        days = sum(e.amount for e in own if e.kind == "day")
        bonus = sum(e.amount for e in own if e.kind == "bonus")
        deduction = sum(e.amount for e in own if e.kind == "deduction")
        paid = sum(e.amount for e in own if e.kind in ("advance", "payment"))
        earned = (staff.salary_rate * days if staff.salary_type == "daily" else staff.salary_rate) + bonus - deduction
        result.append({"staffId": staff.id, "name": staff.name, "salaryType": staff.salary_type, "salaryRate": staff.salary_rate, "days": days, "earned": earned, "paid": paid, "remaining": earned - paid})
    return result


@app.get("/api/debts")
def list_debts(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    debts = ctx.db.scalars(select(Debt).where(Debt.company_id == ctx.cid).order_by(Debt.id.desc())).all()
    return [{"id": d.id, "orderId": d.order_id, "customer": d.customer, "phone": d.phone, "note": d.note, "total": d.total, "paid": d.paid, "remaining": d.total - d.paid, "createdAt": d.created_at} for d in debts]


class DebtPaymentIn(BaseModel):
    amount: int = Field(gt=0)
    method: Literal["naqd", "karta", "payme", "click"]
    note: str = Field(default="", max_length=256)


@app.post("/api/debts/{debt_id}/payments")
def pay_debt(debt_id: int, body: DebtPaymentIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    debt = ctx.db.get(Debt, debt_id)
    if not debt or debt.company_id != ctx.cid:
        raise HTTPException(404, "Qarz topilmadi")
    if body.amount > debt.total - debt.paid:
        raise HTTPException(400, "To'lov qarz qoldig'idan oshmasin")
    shift = open_shift(ctx.db, ctx.cid)
    if not shift:
        raise HTTPException(409, "Qarz to‘lovini qabul qilish uchun avval smenani oching")
    debt.paid += body.amount
    ctx.db.add(DebtPayment(company_id=ctx.cid, debt_id=debt.id, shift_id=shift.id, amount=body.amount, method=body.method, note=body.note))
    ctx.db.commit()
    return {"remaining": debt.total - debt.paid}


@app.get("/api/debts/{debt_id}/payments")
def debt_payment_history(debt_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    debt = ctx.db.get(Debt, debt_id)
    if not debt or debt.company_id != ctx.cid:
        raise HTTPException(404, "Qarz topilmadi")
    payments = ctx.db.scalars(select(DebtPayment).where(DebtPayment.company_id == ctx.cid, DebtPayment.debt_id == debt_id).order_by(DebtPayment.id.desc())).all()
    return [{"id": p.id, "amount": p.amount, "method": p.method, "note": p.note, "createdAt": p.created_at} for p in payments]


# ---------- daily expenses ----------

class ExpenseIn(BaseModel):
    amount: int = Field(gt=0, le=1_000_000_000)
    category: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=500)
    method: Literal["naqd", "karta", "payme", "click"] = "naqd"
    salaryStaffId: int | None = None


def expense_out(e: Expense) -> dict:
    return {"id": e.id, "amount": e.amount, "category": e.category, "note": e.note,
            "method": e.method, "staffName": e.staff_name, "createdAt": e.created_at, "shiftId": e.shift_id}


@app.get("/api/expenses")
def list_expenses(ctx: Ctx = Depends(require(*CASHIERS))) -> list[dict]:
    q = select(Expense).where(Expense.company_id == ctx.cid).order_by(Expense.created_at.desc()).limit(500)
    return [expense_out(e) for e in ctx.db.scalars(q)]


@app.post("/api/expenses")
def create_expense(body: ExpenseIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    shift = open_shift(ctx.db, ctx.cid)
    if body.method == "naqd" and not shift:
        raise HTTPException(409, "Naqd chiqim uchun avval smenani oching")
    category = body.category.strip()
    if category == "Oylik":
        if body.salaryStaffId is None:
            raise HTTPException(400, "Oylik oladigan xodimni tanlang")
        staff = ctx.db.get(Staff, body.salaryStaffId)
        if not staff or staff.company_id != ctx.cid:
            raise HTTPException(404, "Xodim topilmadi")
        ctx.db.add(SalaryEntry(company_id=ctx.cid, staff_id=staff.id, kind="payment", amount=body.amount, note=("Kassadan oylik; bergan: " + ctx.staff.name + "; " + body.note.strip())[:256]))
    e = Expense(company_id=ctx.cid, shift_id=shift.id if shift else None,
                amount=body.amount, category=body.category.strip(), note=body.note.strip(),
                method=body.method, staff_name=ctx.staff.name)
    ctx.db.add(e)
    ctx.db.commit()
    ctx.db.refresh(e)
    return expense_out(e)
