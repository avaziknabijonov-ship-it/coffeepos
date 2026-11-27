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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import seed
from .db import (
    Base, BonusConfig, BonusLedger, Category, ChecklistRun, ChecklistTemplate, DiningTable, Hall, KitchenTicket, OpenCheck, Promotion, RecurringPayment, Workshop, Company, Customer, Expense, StaffPayment, Ingredient, Inventory, Modifier, Order, Product, PurchaseInvoice, Subscription, PayrollPlan, SessionLocal, Shift, Staff, StockConfig, StockMove, engine, now_ms,
)
from .notify import low_stock_crossings, send_low_stock_alert
from .logic import apply_promotions, build_item, round100
from .security import LoginLimiter, check_pin, hash_pin, make_token, read_token

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Tashkent"))
Role = Literal["owner", "admin", "kassir", "barista", "ofitsiant"]
MANAGERS = ("owner", "admin")
CASHIERS = ("owner", "admin", "kassir")
BARISTAS = ("owner", "admin", "barista")
WAITERS = ("owner", "admin", "kassir", "ofitsiant")



def migrate() -> None:
    """Add columns introduced after a table was first created (no Alembic yet)."""
    have = {c["name"] for c in inspect(engine).get_columns("stock_moves")}
    with engine.begin() as conn:
        if "note" not in have:
            conn.execute(text("ALTER TABLE stock_moves ADD COLUMN note VARCHAR(32)"))
        if "inventory_id" not in have:
            conn.execute(text("ALTER TABLE stock_moves ADD COLUMN inventory_id INTEGER"))
    purchase_columns = {c["name"] for c in inspect(engine).get_columns("purchase_invoices")}
    with engine.begin() as conn:
        if "status" not in purchase_columns:
            conn.execute(text("ALTER TABLE purchase_invoices ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active'"))
        if "cancelled_at" not in purchase_columns:
            conn.execute(text("ALTER TABLE purchase_invoices ADD COLUMN cancelled_at BIGINT"))
        if "cancelled_by" not in purchase_columns:
            conn.execute(text("ALTER TABLE purchase_invoices ADD COLUMN cancelled_by VARCHAR(64)"))
    staff_columns = {c["name"] for c in inspect(engine).get_columns("staff")}
    if "can_barista" not in staff_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE staff ADD COLUMN can_barista BOOLEAN NOT NULL DEFAULT FALSE"))
    staff_permissions = {c["name"] for c in inspect(engine).get_columns("staff")}
    with engine.begin() as conn:
        if "can_cancel_orders" not in staff_permissions:
            conn.execute(text("ALTER TABLE staff ADD COLUMN can_cancel_orders BOOLEAN NOT NULL DEFAULT FALSE"))
        if "can_reprint_receipts" not in staff_permissions:
            conn.execute(text("ALTER TABLE staff ADD COLUMN can_reprint_receipts BOOLEAN NOT NULL DEFAULT FALSE"))
    product_columns = {c["name"] for c in inspect(engine).get_columns("products")}
    if "image_url" not in product_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(512) NOT NULL DEFAULT ''"))
    order_columns = {c["name"] for c in inspect(engine).get_columns("orders")}
    with engine.begin() as conn:
        if "cancelled_at" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN cancelled_at BIGINT"))
        if "cancelled_by" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN cancelled_by VARCHAR(64)"))
        if "cancel_reason" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN cancel_reason VARCHAR(256)"))
        if "customer_id" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN customer_id INTEGER"))
        if "bonus_used" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN bonus_used BIGINT NOT NULL DEFAULT 0"))
        if "bonus_earned" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN bonus_earned BIGINT NOT NULL DEFAULT 0"))
        if "client_key" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN client_key VARCHAR(64)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_company_client_key ON orders (company_id, client_key)"))
    category_columns = {c["name"] for c in inspect(engine).get_columns("categories")}
    if "workshop" not in category_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN workshop VARCHAR(64) NOT NULL DEFAULT ''"))
    ingredient_columns = {c["name"] for c in inspect(engine).get_columns("ingredients")}
    with engine.begin() as conn:
        if "recipe" not in ingredient_columns:
            conn.execute(text("ALTER TABLE ingredients ADD COLUMN recipe JSON NOT NULL DEFAULT '[]'"))
        if "yield_qty" not in ingredient_columns:
            conn.execute(text("ALTER TABLE ingredients ADD COLUMN yield_qty FLOAT NOT NULL DEFAULT 0"))


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
    if os.environ.get("ENFORCE_LICENSES", "0") == "1":
        subscription = db.get(Subscription, staff.company_id)
        if not subscription or subscription.status != "active" or subscription.expires_at <= now_ms():
            raise HTTPException(403, "Obuna faol emas. Administratorga murojaat qiling")
    return Ctx(db, staff, db.get(Company, staff.company_id))


def require(*roles: str):
    def dep(ctx: Ctx = Depends(auth)) -> Ctx:
        if ctx.staff.role not in roles:
            raise HTTPException(403, "Bu amal uchun ruxsat yo'q")
        return ctx

    return dep


# ---------- serializers ----------

def staff_out(s: Staff) -> dict:
    return {"id": s.id, "name": s.name, "role": s.role, "active": s.active, "canBarista": bool(s.can_barista), "canCancelOrders": bool(s.can_cancel_orders), "canReprintReceipts": bool(s.can_reprint_receipts)}


def order_out(o: Order) -> dict:
    return {
        "id": str(o.id), "number": o.number, "customer": o.customer, "items": o.items,
        "subtotal": o.subtotal, "discount": o.discount, "total": o.total, "cost": o.cost,
        "payment": o.payment, "cashGiven": o.cash_given, "status": o.status,
        "bonusUsed": o.bonus_used, "bonusEarned": o.bonus_earned,
        "cancelledAt": o.cancelled_at, "cancelledBy": o.cancelled_by, "cancelReason": o.cancel_reason,
        "createdAt": o.created_at, "readyAt": o.ready_at, "barista": o.staff_name, "shiftId": o.shift_id,
    }


def ingredient_out(i: Ingredient) -> dict:
    return {
        "id": i.key, "name": i.name, "unit": i.unit, "cost": i.cost, "stock": i.stock, "min": i.min,
        "recipe": list(i.recipe or []), "yieldQty": i.yield_qty or 0, "semi": bool(i.recipe),
    }


def product_out(p: Product) -> dict:
    return {"id": p.key, "cat": p.cat, "name": p.name, "imageUrl": p.image_url, "mods": p.mods, "sizes": p.sizes, "active": p.active}


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
    for i, (key, cname) in enumerate(seed.CATEGORIES):
        db.add(Category(company_id=cid, key=key, name=cname, sort=i))
    for key, iname, unit, cost, stock, mn in seed.INGREDIENTS:
        db.add(Ingredient(company_id=cid, key=key, name=iname, unit=unit, cost=0, stock=0, min=mn))
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
    if staff and os.environ.get("ENFORCE_LICENSES", "0") == "1":
        subscription = db.get(Subscription, company.id)
        if not subscription or subscription.status != "active" or subscription.expires_at <= now_ms():
            raise HTTPException(403, "Obuna faol emas. Administratorga murojaat qiling")
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
    if os.environ.get("ALLOW_PUBLIC_REGISTRATION", "0") != "1":
        raise HTTPException(403, "Ro'yxatdan o'tish uchun administratorga murojaat qiling")
    if db.scalar(select(Company).where(Company.slug == body.slug)):
        raise HTTPException(409, "Bu login band, boshqasini tanlang")
    create_company(db, body.slug, body.companyName.strip(), body.ownerName.strip(), body.ownerPin)
    db.commit()
    return login(LoginIn(company=body.slug, pin=body.ownerPin), request, db)


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
        "categories": [{"id": c.key, "name": c.name, "workshop": c.workshop or ""} for c in cats],
        "workshops": [{"id": w.key, "name": w.name} for w in sorted(rows(db, Workshop, cid), key=lambda w: (w.sort, w.id))],
        "products": [product_out(p) for p in prods],
        "modifiers": [{"id": m.key, "group": m.group, "name": m.name, "price": m.price, "effect": m.effect} for m in mods],
        "ingredients": [ingredient_out(i) for i in rows(db, Ingredient, cid)],
        "settings": {"autoStoplist": stock_settings(db, cid).auto_stoplist},
        "promotions": [promotion_out(p) for p in rows(db, Promotion, cid) if p.active],
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


@app.put("/api/categories/{key}")
def rename_category(key: str, body: CategoryIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    cat = get_row(ctx.db, Category, ctx.cid, key)
    cat.name = body.name.strip()
    ctx.db.commit()
    return {"id": cat.key, "name": cat.name}


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
    imageUrl: str = Field(default="", max_length=512)
    mods: list[Literal["milk", "syrup", "shot"]] = []
    sizes: list[SizeIn] = Field(min_length=1)
    active: bool = True


def validate_product(ctx: Ctx, body: ProductIn) -> None:
    if body.imageUrl and not (body.imageUrl.startswith("https://") or body.imageUrl.startswith("/assets/")):
        raise HTTPException(422, "Rasm uchun HTTPS yoki ichki /assets/ manzilini kiriting")
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
        company_id=ctx.cid, key=slugify(body.name), cat=body.cat, name=body.name.strip(), image_url=body.imageUrl, mods=body.mods,
        sizes=[s.model_dump() for s in body.sizes], active=body.active, sort=len(rows(ctx.db, Product, ctx.cid)),
    )
    ctx.db.add(p)
    ctx.db.commit()
    return product_out(p)


@app.put("/api/products/{key}")
def update_product(key: str, body: ProductIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    p = get_row(ctx.db, Product, ctx.cid, key)
    validate_product(ctx, body)
    p.cat, p.name, p.mods = body.cat, body.name.strip(), body.mods
    p.image_url = body.imageUrl
    p.sizes, p.active = [s.model_dump() for s in body.sizes], body.active
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
    # Polufabrikat: components per batch, and how many units one batch yields.
    recipe: list[RecipeLineIn] = Field(default=[], max_length=30)
    yieldQty: float = Field(default=0, ge=0)


def semi_unit_cost(recipe: list[dict], yield_qty: float, ings: dict[str, Ingredient]) -> float:
    if not recipe or yield_qty <= 0:
        return 0.0
    return sum(ings[l["ing"]].cost * l["qty"] for l in recipe if l["ing"] in ings) / yield_qty


def validate_semi(ctx: Ctx, body: IngredientIn, self_key: str | None) -> list[dict]:
    """Return a clean recipe list; raw ingredients get an empty one."""
    if not body.recipe:
        return []
    if body.yieldQty <= 0:
        raise HTTPException(400, "Polufabrikat chiqishi (miqdori) 0 dan katta bo'lsin")
    ings = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    seen: set[str] = set()
    for line in body.recipe:
        comp = ings.get(line.ing)
        if comp is None:
            raise HTTPException(400, "Polufabrikat tarkibida noma'lum xomashyo")
        if line.ing == self_key:
            raise HTTPException(400, "Polufabrikat o'zini tarkibiga kiritolmaydi")
        if comp.recipe:
            raise HTTPException(400, "Polufabrikat tarkibiga boshqa polufabrikat qo'shib bo'lmaydi")
        if line.ing in seen:
            raise HTTPException(400, "Tarkibda xomashyo takrorlangan")
        seen.add(line.ing)
    if self_key is not None:
        used_in = [i.name for i in ings.values() if any(l.get("ing") == self_key for l in (i.recipe or []))]
        if used_in:
            raise HTTPException(409, f"Bu xomashyo {used_in[0]} tarkibida ishlatiladi, polufabrikat qilib bo'lmaydi")
    return [{"ing": l.ing, "qty": l.qty} for l in body.recipe]


@app.post("/api/ingredients")
def add_ingredient(body: IngredientIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    recipe = validate_semi(ctx, body, None)
    i = Ingredient(company_id=ctx.cid, key=slugify(body.name), stock=0, name=body.name.strip(), unit=body.unit,
                   cost=body.cost, min=body.min, recipe=recipe, yield_qty=body.yieldQty if recipe else 0)
    if recipe:
        i.cost = semi_unit_cost(recipe, i.yield_qty, {x.key: x for x in rows(ctx.db, Ingredient, ctx.cid)})
    ctx.db.add(i)
    ctx.db.commit()
    return ingredient_out(i)


@app.put("/api/ingredients/{key}")
def update_ingredient(key: str, body: IngredientIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    i = get_row(ctx.db, Ingredient, ctx.cid, key)
    recipe = validate_semi(ctx, body, key)
    i.name, i.unit, i.min = body.name.strip(), body.unit, body.min
    i.recipe, i.yield_qty = recipe, body.yieldQty if recipe else 0
    if recipe:
        # Semi cost comes from production; before the first batch show the recipe cost.
        if i.stock <= 0.000001:
            i.cost = semi_unit_cost(recipe, i.yield_qty, {x.key: x for x in rows(ctx.db, Ingredient, ctx.cid)})
    else:
        i.cost = body.cost
    ctx.db.commit()
    return ingredient_out(i)


class ProductionIn(BaseModel):
    ing: str
    qty: float = Field(gt=0, le=1_000_000)


@app.post("/api/production")
def produce_semi(body: ProductionIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    """Make a batch of a semi-finished item: components leave stock, the semi item enters it."""
    db, cid = ctx.db, ctx.cid
    ings = {i.key: i for i in db.scalars(select(Ingredient).where(Ingredient.company_id == cid).with_for_update())}
    semi = ings.get(body.ing)
    if semi is None:
        raise HTTPException(404, "Topilmadi")
    if not semi.recipe or semi.yield_qty <= 0:
        raise HTTPException(400, "Bu xomashyo polufabrikat emas")
    factor = body.qty / semi.yield_qty
    needs = [(ings.get(l["ing"]), l["qty"] * factor) for l in semi.recipe]
    if any(comp is None for comp, _ in needs):
        raise HTTPException(409, "Polufabrikat tarkibidagi xomashyo topilmadi")
    if stock_settings(db, cid).auto_stoplist:
        short = [comp.name for comp, need in needs if comp.stock + 0.000001 < need]
        if short:
            raise HTTPException(409, f"Omborda yetarli emas: {', '.join(short)}")
    before = {k: v.stock for k, v in ings.items()}
    batch_cost = 0.0
    for comp, need in needs:
        comp.stock -= need
        batch_cost += comp.cost * need
        db.add(StockMove(company_id=cid, ingredient=comp.key, qty=-need, reason="prod_use",
                         note=semi.key[:32], staff_name=ctx.staff.name))
    old_stock = max(semi.stock, 0.0)
    unit_cost = batch_cost / body.qty
    semi.cost = (old_stock * semi.cost + batch_cost) / (old_stock + body.qty) if old_stock > 0 else unit_cost
    semi.stock += body.qty
    db.add(StockMove(company_id=cid, ingredient=semi.key, qty=body.qty, reason="production",
                     staff_name=ctx.staff.name))
    db.commit()
    alert_low_stock(db, cid, before, ings.values())
    return ingredient_out(semi)


# ---------- stock automation settings ----------

def stock_settings(db: Session, cid: int, create: bool = False) -> StockConfig:
    config = db.get(StockConfig, cid)
    if config is None:
        config = StockConfig(company_id=cid, auto_stoplist=False, telegram_token="", telegram_chat="")
        if create:
            db.add(config)
    return config


def stock_config_out(c: StockConfig) -> dict:
    return {"autoStoplist": bool(c.auto_stoplist), "telegramChat": c.telegram_chat or "",
            "telegramConfigured": bool(c.telegram_token and c.telegram_chat)}


class StockConfigIn(BaseModel):
    autoStoplist: bool
    telegramChat: str = Field(default="", max_length=64, pattern=r"^(-?\d{1,20}|@[A-Za-z0-9_]{4,60})?$")
    # None keeps the saved token; "" removes it. The token is never sent back to the browser.
    telegramToken: str | None = Field(default=None, max_length=128, pattern=r"^(\d{5,15}:[A-Za-z0-9_-]{20,100})?$")


@app.get("/api/stock/config")
def stock_config_get(ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    return stock_config_out(stock_settings(ctx.db, ctx.cid))


@app.put("/api/stock/config")
def stock_config_put(body: StockConfigIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    config = stock_settings(ctx.db, ctx.cid, create=True)
    config.auto_stoplist = body.autoStoplist
    config.telegram_chat = body.telegramChat.strip()
    if body.telegramToken is not None:
        config.telegram_token = body.telegramToken.strip()
    ctx.db.commit()
    return stock_config_out(config)


def alert_low_stock(db: Session, cid: int, before: dict[str, float], after) -> None:
    """Send a Telegram message for ingredients that just dropped below their minimum."""
    crossed = low_stock_crossings(before, after)
    if not crossed:
        return
    config = db.get(StockConfig, cid)
    if config is None or not config.telegram_token or not config.telegram_chat:
        return
    company = db.get(Company, cid)
    send_low_stock_alert(config.telegram_token, config.telegram_chat, company.name if company else "", crossed)


@app.delete("/api/ingredients/{key}")
def delete_ingredient(key: str, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Delete only an unused zero-stock ingredient; preserve financial history."""
    db = ctx.db
    ing = get_row(db, Ingredient, ctx.cid, key)
    if abs(ing.stock) > 0.000001:
        raise HTTPException(409, "Avval mahsulot qoldig'ini 0 qiling")
    purchases = db.scalars(select(PurchaseInvoice).where(PurchaseInvoice.company_id == ctx.cid)).all()
    if any(line.get("ing") == key for purchase in purchases for line in purchase.lines):
        raise HTTPException(409, "Mahsulot kirim hujjatlarida bor, tarixni saqlash uchun o'chirib bo'lmaydi")
    moves = db.scalars(select(StockMove).where(StockMove.company_id == ctx.cid, StockMove.ingredient == key)).first()
    if moves is not None:
        raise HTTPException(409, "Mahsulot ombor harakatlari tarixida bor")
    products = db.scalars(select(Product).where(Product.company_id == ctx.cid)).all()
    if any(ingredient.get("ing") == key for product in products for size in product.sizes for ingredient in size.get("recipe", [])):
        raise HTTPException(409, "Mahsulot texkartada ishlatiladi; avval texkartadan olib tashlang")
    if any(line.get("ing") == key for other in rows(db, Ingredient, ctx.cid) for line in (other.recipe or [])):
        raise HTTPException(409, "Mahsulot polufabrikat tarkibida ishlatiladi; avval tarkibdan olib tashlang")
    db.delete(ing)
    db.commit()
    return {"ok": True}


WRITEOFF_NOTES = ("spill", "expired", "staff", "broken", "other")


class StockIn(BaseModel):
    ing: str
    qty: float
    reason: Literal["intake", "writeoff", "count"]
    note: Literal[WRITEOFF_NOTES] | None = None


@app.post("/api/stock")
def stock_move(body: StockIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    if body.reason == "intake":
        raise HTTPException(400, "Kirim faqat nakladnoy orqali qilinadi")
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
    before = {i.key: i.stock}
    i.stock += delta
    ctx.db.add(StockMove(company_id=ctx.cid, ingredient=i.key, qty=delta, reason=body.reason, note=note, staff_name=ctx.staff.name))
    ctx.db.commit()
    alert_low_stock(ctx.db, ctx.cid, before, [i])
    return ingredient_out(i)


class PurchaseLineIn(BaseModel):
    ing: str
    qty: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class PurchaseInvoiceIn(BaseModel):
    number: str = Field(min_length=1, max_length=64)
    supplier: str = Field(min_length=1, max_length=128)
    received_at: int = Field(gt=0)
    payment_status: Literal["paid", "unpaid", "partial"] = "unpaid"
    note: str = Field(default="", max_length=500)
    lines: list[PurchaseLineIn] = Field(min_length=1)


def purchase_out(p: PurchaseInvoice) -> dict:
    return {
        "id": p.id, "number": p.number, "supplier": p.supplier,
        "receivedAt": p.received_at, "paymentStatus": p.payment_status,
        "note": p.note, "lines": p.lines, "total": p.total,
        "staff": p.staff_name, "createdAt": p.created_at,
        "status": p.status, "cancelledAt": p.cancelled_at, "cancelledBy": p.cancelled_by,
    }


@app.get("/api/purchases")
def list_purchases(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(PurchaseInvoice).where(PurchaseInvoice.company_id == ctx.cid).order_by(PurchaseInvoice.id.desc()).limit(200)
    return [purchase_out(p) for p in ctx.db.scalars(q)]


class PurchaseDetailsUpdate(BaseModel):
    number: str = Field(min_length=1, max_length=64)
    supplier: str = Field(min_length=1, max_length=128)
    received_at: int = Field(gt=0)
    note: str = Field(default="", max_length=500)


@app.put("/api/purchases/{purchase_id}")
def update_purchase_details(purchase_id: int, body: PurchaseDetailsUpdate, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    inv = ctx.db.get(PurchaseInvoice, purchase_id)
    if inv is None or inv.company_id != ctx.cid:
        raise HTTPException(404, "Nakladnoy topilmadi")
    if inv.status == "cancelled":
        raise HTTPException(409, "Bekor qilingan nakladnoyni tahrirlab bo'lmaydi")
    duplicate = ctx.db.scalar(select(PurchaseInvoice).where(
        PurchaseInvoice.company_id == ctx.cid,
        PurchaseInvoice.number == body.number.strip(),
        PurchaseInvoice.id != purchase_id
    ))
    if duplicate:
        raise HTTPException(409, "Bu nakladnoy raqami allaqachon mavjud")
    inv.number = body.number.strip()
    inv.supplier = body.supplier.strip()
    inv.received_at = body.received_at
    inv.note = body.note.strip()
    ctx.db.commit()
    return purchase_out(inv)


@app.post("/api/purchases/{purchase_id}/cancel")
def cancel_purchase(purchase_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    db = ctx.db
    inv = db.scalar(select(PurchaseInvoice).where(
        PurchaseInvoice.company_id == ctx.cid, PurchaseInvoice.id == purchase_id
    ).with_for_update())
    if inv is None:
        raise HTTPException(404, "Nakladnoy topilmadi")
    if inv.status != "active":
        raise HTTPException(409, "Nakladnoy allaqachon bekor qilingan")
    ingredients = {i.key: i for i in db.scalars(select(Ingredient).where(
        Ingredient.company_id == ctx.cid
    ).with_for_update())}
    for line in inv.lines:
        ing = ingredients.get(line["ing"])
        if ing is None or ing.stock + 0.000001 < line["qty"]:
            raise HTTPException(409, "Omborda yetarli qoldiq yo'q; avval inventarizatsiya qiling")
    for line in inv.lines:
        ing = ingredients[line["ing"]]
        before = ing.stock
        qty = line["qty"]
        remaining = before - qty
        if remaining > 0.000001:
            ing.cost = max(0.0, (before * ing.cost - qty * line["unitPrice"]) / remaining)
        ing.stock = max(0.0, remaining)
        db.add(StockMove(company_id=ctx.cid, ingredient=ing.key, qty=-qty,
                         reason="purchase_cancel", staff_name=ctx.staff.name,
                         note=str(inv.id)[:32]))
    inv.status = "cancelled"
    inv.cancelled_at = now_ms()
    inv.cancelled_by = ctx.staff.name
    db.commit()
    return purchase_out(inv)


@app.post("/api/purchases")
def create_purchase(body: PurchaseInvoiceIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    db = ctx.db
    if db.scalar(select(PurchaseInvoice).where(PurchaseInvoice.company_id == ctx.cid, PurchaseInvoice.number == body.number.strip())):
        raise HTTPException(409, "Bu nakladnoy raqami allaqachon mavjud")
    keys = [l.ing for l in body.lines]
    if len(keys) != len(set(keys)):
        raise HTTPException(400, "Bir xil xomashyoni bitta satrda kiriting")
    ings = {i.key: i for i in rows(db, Ingredient, ctx.cid)}
    validated = []
    for l in body.lines:
        ing = ings.get(l.ing)
        if ing is None:
            raise HTTPException(404, f"Xomashyo topilmadi: {l.ing}")
        subtotal = round(l.qty * l.unit_price)
        validated.append({"ing": ing.key, "name": ing.name, "unit": ing.unit, "qty": l.qty, "unitPrice": l.unit_price, "subtotal": subtotal})
    inv = PurchaseInvoice(company_id=ctx.cid, number=body.number.strip(), supplier=body.supplier.strip(),
                          received_at=body.received_at, payment_status=body.payment_status, note=body.note.strip(),
                          lines=validated, total=sum(l["subtotal"] for l in validated), staff_name=ctx.staff.name)
    db.add(inv)
    db.flush()
    for l in validated:
        ing = ings[l["ing"]]
        old_stock = ing.stock
        ing.stock += l["qty"]
        ing.cost = (old_stock * ing.cost + l["qty"] * l["unitPrice"]) / (old_stock + l["qty"]) if old_stock > 0 else l["unitPrice"]
        db.add(StockMove(company_id=ctx.cid, ingredient=ing.key, qty=l["qty"], reason="intake",
                         staff_name=ctx.staff.name, note=None))
    db.commit()
    return purchase_out(inv)


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
def losses_report(days: int = 30, date_from: str | None = None, date_to: str | None = None, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Write-offs by cause and ingredient, plus stocktake shortage/surplus, valued at current cost."""
    since = start_of_day_ms(days)
    until = None
    if date_from is not None or date_to is not None:
        if not date_from or not date_to:
            raise HTTPException(400, "Ikkala sanani kiriting")
        try:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "Sana formati noto'g'ri")
        if end_date < start_date or (end_date - start_date).days > 3660:
            raise HTTPException(400, "Sana oralig'i noto'g'ri")
        since = int(start_date.replace(tzinfo=TZ).timestamp() * 1000)
        until = int((end_date + timedelta(days=1)).replace(tzinfo=TZ).timestamp() * 1000)
    ings = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    moves = ctx.db.scalars(
        select(StockMove).where(
            StockMove.company_id == ctx.cid, StockMove.reason.in_(("writeoff", "count")), StockMove.created_at >= since
        )
    )
    by_note: dict[str, int] = {}
    by_ing: dict[str, dict] = {}
    for m in moves:
        if until is not None and m.created_at >= until:
            continue
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
    iq = select(Inventory).where(Inventory.company_id == ctx.cid, Inventory.created_at >= since)
    if until is not None:
        iq = iq.where(Inventory.created_at < until)
    invs = ctx.db.scalars(iq).all()
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


# ---------- expense records ----------
class ExpenseIn(BaseModel):
    amount: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=256)
    payment: Literal["cash", "card", "bank"] = "cash"


@app.get("/api/expenses")
def expenses(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(Expense).where(Expense.company_id == ctx.cid).order_by(Expense.id.desc()).limit(250)
    return [{"id": e.id, "amount": e.amount, "category": e.category, "description": e.description,
             "payment": e.payment, "staff": e.staff_name, "createdAt": e.created_at} for e in ctx.db.scalars(q)]


@app.post("/api/expenses")
def add_expense(body: ExpenseIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    if ctx.staff.role == "kassir" and open_shift(ctx.db, ctx.cid) is None:
        raise HTTPException(409, "Xarajat kiritish uchun smena ochiq bo'lishi kerak")
    e = Expense(company_id=ctx.cid, amount=body.amount, category=body.category.strip(),
                description=body.description.strip(), payment=body.payment, staff_name=ctx.staff.name)
    ctx.db.add(e)
    ctx.db.commit()
    ctx.db.refresh(e)
    return {"id": e.id}


class StaffPaymentIn(BaseModel):
    staff_id: int
    amount: int = Field(gt=0)
    note: str = Field(default="", max_length=256)


@app.get("/api/staff-payments")
def staff_payments(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(StaffPayment).where(StaffPayment.company_id == ctx.cid).order_by(StaffPayment.id.desc()).limit(250)
    return [{"id": p.id, "staffId": p.staff_id, "amount": p.amount, "note": p.note,
             "recordedBy": p.recorded_by, "createdAt": p.created_at} for p in ctx.db.scalars(q)]


@app.post("/api/staff-payments")
def add_staff_payment(body: StaffPaymentIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    member = ctx.db.get(Staff, body.staff_id)
    if member is None or member.company_id != ctx.cid:
        raise HTTPException(404, "Xodim topilmadi")
    p = StaffPayment(company_id=ctx.cid, staff_id=member.id, amount=body.amount,
                     note=body.note.strip(), recorded_by=ctx.staff.name)
    ctx.db.add(p)
    ctx.db.commit()
    ctx.db.refresh(p)
    return {"id": p.id}


# ---------- staff salary and advance accounting ----------
class PayrollPlanIn(BaseModel):
    monthly_salary: int = Field(ge=0, le=1_000_000_000)
    standard_days: int = Field(default=26, ge=1, le=31)
    worked_days: float = Field(default=0, ge=0, le=31)
    deductions: int = Field(default=0, ge=0, le=1_000_000_000)
    note: str = Field(default="", max_length=256)


def month_bounds(month: str) -> tuple[int, int]:
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(422, "Oy YYYY-MM formatida bo'lishi kerak")
    y, m = [int(v) for v in month.split("-")]
    if not 2000 <= y <= 2100:
        raise HTTPException(422, "Yil noto'g'ri")
    lo = datetime(y, m, 1, tzinfo=TZ)
    hi = datetime(y + 1, 1, 1, tzinfo=TZ) if m == 12 else datetime(y, m + 1, 1, tzinfo=TZ)
    return int(lo.timestamp() * 1000), int(hi.timestamp() * 1000)


@app.get("/api/payroll")
def payroll_get(month: str, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    lo, hi = month_bounds(month)
    db, cid = ctx.db, ctx.cid
    plans = {p.staff_id: p for p in db.scalars(select(PayrollPlan).where(
        PayrollPlan.company_id == cid, PayrollPlan.month == month
    ))}
    payouts: dict[int, int] = {}
    for payment in db.scalars(select(StaffPayment).where(
        StaffPayment.company_id == cid,
        StaffPayment.created_at >= lo,
        StaffPayment.created_at < hi,
    )):
        payouts[payment.staff_id] = payouts.get(payment.staff_id, 0) + payment.amount
    items = []
    for person in rows(db, Staff, cid):
        plan = plans.get(person.id)
        salary = plan.monthly_salary if plan else 0
        work = plan.worked_days if plan else 0
        norm = plan.standard_days if plan else 26
        deduct = plan.deductions if plan else 0
        earned = round(salary * work / norm)
        paid = payouts.get(person.id, 0)
        balance = earned - deduct - paid
        items.append({
            "staffId": person.id, "name": person.name, "role": person.role,
            "monthlySalary": salary, "standardDays": norm, "workedDays": work,
            "deductions": deduct, "paid": paid, "earned": earned,
            "toPay": max(0, balance), "overpaid": max(0, -balance),
            "note": plan.note if plan else "",
        })
    return {"month": month, "items": items}


@app.put("/api/payroll/{staff_id}/{month}")
def payroll_set(staff_id: int, month: str, body: PayrollPlanIn,
                ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    month_bounds(month)
    person = ctx.db.get(Staff, staff_id)
    if person is None or person.company_id != ctx.cid:
        raise HTTPException(404, "Xodim topilmadi")
    if body.worked_days > body.standard_days:
        raise HTTPException(422, "Ishlangan kun me'yoridan ko'p")
    plan = ctx.db.scalar(select(PayrollPlan).where(
        PayrollPlan.company_id == ctx.cid,
        PayrollPlan.staff_id == staff_id, PayrollPlan.month == month,
    ))
    if plan is None:
        plan = PayrollPlan(company_id=ctx.cid, staff_id=staff_id, month=month)
        ctx.db.add(plan)
    plan.monthly_salary = body.monthly_salary
    plan.standard_days = body.standard_days
    plan.worked_days = body.worked_days
    plan.deductions = body.deductions
    plan.note = body.note.strip()
    plan.updated_at = now_ms()
    ctx.db.commit()
    return {"ok": True, "staffId": staff_id, "month": month}


# ---------- CoffeePOS loyalty ----------
class BonusSettingsIn(BaseModel):
    enabled: bool
    earn_percent: int = Field(ge=0, le=20)
    redemption_limit_percent: int = Field(ge=0, le=50)


def bonus_settings(db: Session, cid: int) -> BonusConfig:
    config = db.get(BonusConfig, cid)
    if config is None:
        config = BonusConfig(company_id=cid, enabled=False, earn_percent=5,
                             redemption_limit_percent=30)
        db.add(config)
        db.flush()
    return config


@app.get("/api/bonus/config")
def bonus_config_get(ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    config = bonus_settings(ctx.db, ctx.cid)
    return {"enabled": config.enabled, "earnPercent": config.earn_percent,
            "redemptionLimitPercent": config.redemption_limit_percent}


@app.put("/api/bonus/config")
def bonus_config_put(body: BonusSettingsIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    config = bonus_settings(ctx.db, ctx.cid)
    config.enabled = body.enabled
    config.earn_percent = body.earn_percent
    config.redemption_limit_percent = body.redemption_limit_percent
    ctx.db.commit()
    return {"enabled": config.enabled, "earnPercent": config.earn_percent,
            "redemptionLimitPercent": config.redemption_limit_percent}


@app.get("/api/bonus/customers/{phone}")
def bonus_customer_get(phone: str, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    if not re.fullmatch(r"\+?[0-9]{9,15}", phone):
        raise HTTPException(422, "Telefon raqami noto'g'ri")
    customer = ctx.db.scalar(select(Customer).where(Customer.company_id == ctx.cid,
                                                      Customer.phone == phone))
    config = bonus_settings(ctx.db, ctx.cid)
    return {"phone": phone, "name": customer.name if customer else "",
            "balance": customer.bonus_balance if customer else 0,
            "enabled": config.enabled, "earnPercent": config.earn_percent,
            "redemptionLimitPercent": config.redemption_limit_percent}


# ---------- staff ----------

class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    role: Role
    pin: str | None = Field(default=None, pattern=PIN_RE)
    active: bool = True
    canBarista: bool = False
    canCancelOrders: bool = False
    canReprintReceipts: bool = False


def guard_owner(ctx: Ctx, role: str) -> None:
    if role == "owner" and ctx.staff.role != "owner":
        raise HTTPException(403, "Faqat rahbar rahbar qo'sha oladi")


@app.get("/api/staff")
def list_staff(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    return [staff_out(s) for s in rows(ctx.db, Staff, ctx.cid)]


@app.post("/api/staff")
def add_staff(body: StaffIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    guard_owner(ctx, body.role)
    if not body.pin:
        raise HTTPException(400, "PIN kerak")
    if pin_taken(ctx.db, ctx.cid, body.pin):
        raise HTTPException(409, "Bu PIN band")
    s = Staff(company_id=ctx.cid, name=body.name.strip(), role=body.role, pin_hash=hash_pin(body.pin), active=body.active, can_barista=body.canBarista if body.role == "kassir" else False, can_cancel_orders=body.canCancelOrders if body.role == "kassir" else False, can_reprint_receipts=body.canReprintReceipts if body.role == "kassir" else False)
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
    s.can_barista = body.canBarista if body.role == "kassir" else False
    s.can_cancel_orders = body.canCancelOrders if body.role == "kassir" else False
    s.can_reprint_receipts = body.canReprintReceipts if body.role == "kassir" else False
    ctx.db.commit()
    return staff_out(s)


# ---------- shifts ----------

class OpenShiftIn(BaseModel):
    openingCash: int = Field(ge=0)


class CloseShiftIn(BaseModel):
    closingCash: int = Field(ge=0)


def shift_summary(db: Session, shift: Shift) -> dict:
    orders = db.scalars(select(Order).where(Order.shift_id == shift.id, Order.status != "cancelled")).all()
    by_payment: dict[str, int] = {}
    for o in orders:
        by_payment[o.payment] = by_payment.get(o.payment, 0) + o.total
    # Cash expenses reduce the physically expected register balance.
    cutoff = shift.closed_at if shift.closed_at is not None else now_ms()
    cash_spent = sum(row.amount for row in db.scalars(select(Expense).where(
        Expense.company_id == shift.company_id,
        Expense.payment == "cash",
        Expense.created_at >= shift.opened_at,
        Expense.created_at <= cutoff,
    )))
    return {
        "shift": shift_out(shift),
        "orders": len(orders),
        "revenue": sum(o.total for o in orders),
        "byPayment": by_payment,
        "cashExpenses": cash_spent,
        "expectedCash": shift.opening_cash + by_payment.get("naqd", 0) - cash_spent,
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
    discountPct: int = Field(default=0, ge=0, le=50)
    payment: Literal["naqd", "karta", "payme", "click"]
    cashGiven: int | None = Field(default=None, ge=0)
    customerPhone: str = Field(default="", max_length=20)
    bonusRedeem: int = Field(default=0, ge=0)
    clientKey: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{12,64}$")
    # Sale already happened while the device was offline: never refuse it for stock.
    offline: bool = False
    # Device time of an offline sale, so happy-hour promotions match when it was sold.
    soldAt: int | None = Field(default=None, gt=0)


@app.get("/api/orders/history")
def orders_history(from_ms: int, to_ms: int, staff: str = "", shift_id: int | None = None,
                   ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    """Auditable order history, filtered within one tenant. Date range max 366 days."""
    if to_ms <= from_ms or to_ms - from_ms > 366 * 86400000:
        raise HTTPException(400, "Sana oralig'i 1-366 kun bo'lishi kerak")
    q = select(Order).where(Order.company_id == ctx.cid, Order.created_at >= from_ms,
                            Order.created_at < to_ms)
    if staff:
        q = q.where(Order.staff_name == staff)
    if shift_id is not None:
        q = q.where(Order.shift_id == shift_id)
    q = q.order_by(Order.created_at.desc()).limit(5000)
    out = []
    for order in ctx.db.scalars(q):
        record = order_out(order)
        record["shiftId"] = order.shift_id
        out.append(record)
    return out


@app.post("/api/orders")
def create_order(body: OrderIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    return place_order(body, ctx)


def place_order(body: OrderIn, ctx: Ctx, status: str = "new", stock_guard: bool = True, on_created=None) -> dict:
    """Validate, price and record a paid sale. `on_created(order)` runs inside the same transaction."""
    db, cid = ctx.db, ctx.cid
    if body.clientKey:
        existing = db.scalar(select(Order).where(
            Order.company_id == cid, Order.client_key == body.clientKey
        ))
        if existing:
            return order_out(existing)
    shift = open_shift(db, cid)
    if not shift:
        raise HTTPException(409, "Avval smenani oching")
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

    used: dict[str, float] = {}
    for it in items:
        for line in it["consumption"]:
            used[line["ing"]] = used.get(line["ing"], 0) + line["qty"] * it["qty"]
    if stock_guard and not body.offline and stock_settings(db, cid).auto_stoplist:
        short = [ings[k].name for k, q in used.items() if k in ings and ings[k].stock + 0.000001 < q]
        if short:
            raise HTTPException(409, f"Qoldiq yetarli emas (stop-list): {', '.join(short)}")

    subtotal = sum(i["unitPrice"] * i["qty"] for i in items)
    sold_at = now_ms()
    if body.offline and body.soldAt and sold_at - 72 * 3600 * 1000 <= body.soldAt <= sold_at + 5 * 60 * 1000:
        sold_at = body.soldAt
    promos = rows(db, Promotion, cid)
    promo_discount = apply_promotions(items, {p.key: p.cat for p in prods.values()}, promos,
                                      datetime.fromtimestamp(sold_at / 1000, TZ))
    discount = promo_discount + round100((subtotal - promo_discount) * body.discountPct / 100)
    total = subtotal - discount
    phone = body.customerPhone.strip()
    customer = None
    earned = 0
    redeemed = 0
    if phone:
        if not re.fullmatch(r"\+?[0-9]{9,15}", phone):
            raise HTTPException(422, "Telefon raqami noto'g'ri")
        config = bonus_settings(db, cid)
        if config.enabled:
            customer = db.scalar(select(Customer).where(
                Customer.company_id == cid, Customer.phone == phone).with_for_update())
            if customer is None:
                customer = Customer(company_id=cid, phone=phone, name=body.customer.strip())
                db.add(customer)
                db.flush()
            limit = (total * config.redemption_limit_percent) // 100
            if body.bonusRedeem > customer.bonus_balance or body.bonusRedeem > limit:
                raise HTTPException(409, "Bonus yetarli emas yoki limit oshirilgan")
            redeemed = body.bonusRedeem
            total -= redeemed
            earned = (total * config.earn_percent) // 100
            customer.bonus_balance += earned - redeemed
        elif body.bonusRedeem:
            raise HTTPException(409, "Bonus tizimi o'chirilgan")
    elif body.bonusRedeem:
        raise HTTPException(422, "Bonus ishlatish uchun mijoz telefoni kerak")
    if body.payment == "naqd" and body.cashGiven is not None and body.cashGiven < total:
        raise HTTPException(400, "Berilgan pul yetarli emas")

    day_orders = db.scalars(
        select(Order.number).where(Order.company_id == cid, Order.created_at >= start_of_day_ms())
    ).all()
    order = Order(
        company_id=cid, shift_id=shift.id, number=max(day_orders, default=0) + 1, customer=body.customer.strip(),
        customer_id=customer.id if customer is not None else None, bonus_used=redeemed, bonus_earned=earned,
        client_key=body.clientKey,
        items=items, subtotal=subtotal, discount=discount, total=total,
        cost=sum(i["unitCost"] * i["qty"] for i in items), payment=body.payment,
        cash_given=body.cashGiven if body.payment == "naqd" else None, staff_name=ctx.staff.name,
        status=status, ready_at=now_ms() if status == "done" else None,
    )
    db.add(order)
    db.flush()
    if on_created is not None:
        on_created(order)
    if customer is not None:
        if redeemed:
            db.add(BonusLedger(company_id=cid, customer_id=customer.id, order_id=order.id,
                               amount=-redeemed, reason="redeem"))
        if earned:
            db.add(BonusLedger(company_id=cid, customer_id=customer.id, order_id=order.id,
                               amount=earned, reason="earn"))
    before = {k: i.stock for k, i in ings.items()}
    for key, qty in used.items():
        if key in ings:
            ings[key].stock -= qty
            db.add(StockMove(company_id=cid, ingredient=key, qty=-qty, reason="sale", order_id=order.id, staff_name=ctx.staff.name))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if body.clientKey:
            duplicate = db.scalar(select(Order).where(
                Order.company_id == cid, Order.client_key == body.clientKey
            ))
            if duplicate:
                return order_out(duplicate)
        raise HTTPException(409, "Bir vaqtning o'zida takroriy buyurtma; qayta tekshiring")
    alert_low_stock(db, cid, before, ings.values())
    return order_out(order)


class CancelOrderIn(BaseModel):
    reason: str = Field(min_length=3, max_length=256)


@app.post("/api/orders/{oid}/cancel")
def cancel_order(oid: int, body: CancelOrderIn, ctx: Ctx = Depends(auth)) -> dict:
    if ctx.staff.role not in MANAGERS and not (ctx.staff.role == "kassir" and ctx.staff.can_cancel_orders):
        raise HTTPException(403, "Otmena uchun dostup berilmagan")
    order = ctx.db.get(Order, oid)
    if order is None or order.company_id != ctx.cid:
        raise HTTPException(404, "Buyurtma topilmadi")
    if order.status != "new":
        raise HTTPException(409, "Faqat hali tayyorlanmagan buyurtmani bekor qilish mumkin")
    shift = open_shift(ctx.db, ctx.cid)
    if shift is None or order.shift_id != shift.id:
        raise HTTPException(409, "Yopilgan smenadagi buyurtmani bekor qilib bo'lmaydi")
    ingredients = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    moves = ctx.db.scalars(select(StockMove).where(
        StockMove.company_id == ctx.cid, StockMove.order_id == order.id, StockMove.reason == "sale"
    )).all()
    for move in moves:
        item = ingredients.get(move.ingredient)
        if item is not None:
            item.stock -= move.qty
            ctx.db.add(StockMove(company_id=ctx.cid, ingredient=move.ingredient,
                                 qty=-move.qty, reason="return", order_id=order.id,
                                 staff_name=ctx.staff.name))
    if order.customer_id is not None:
        customer = ctx.db.scalar(select(Customer).where(
            Customer.id == order.customer_id, Customer.company_id == ctx.cid).with_for_update())
        if customer is not None:
            if customer.bonus_balance < order.bonus_earned:
                raise HTTPException(409, "Mijoz bonusdan foydalangan. Avval bonus hisobini tekshiring")
            customer.bonus_balance += order.bonus_used - order.bonus_earned
            if order.bonus_earned:
                ctx.db.add(BonusLedger(company_id=ctx.cid, customer_id=customer.id,
                                       order_id=order.id, amount=-order.bonus_earned, reason="cancel_earn"))
            if order.bonus_used:
                ctx.db.add(BonusLedger(company_id=ctx.cid, customer_id=customer.id,
                                       order_id=order.id, amount=order.bonus_used, reason="cancel_redeem"))
    order.status = "cancelled"
    order.cancelled_at = now_ms()
    order.cancelled_by = ctx.staff.name
    order.cancel_reason = body.reason.strip()
    ctx.db.commit()
    return order_out(order)


class StatusIn(BaseModel):
    status: Literal["new", "preparing", "ready", "done"]


@app.patch("/api/orders/{oid}")
def set_status(oid: int, body: StatusIn, ctx: Ctx = Depends(auth)) -> dict:
    # Cashiers cannot prepare orders unless a manager explicitly grants barista access.
    if ctx.staff.role not in BARISTAS and not (
        ctx.staff.role == "kassir" and ctx.staff.can_barista
    ):
        raise HTTPException(403, "Barista vazifasi uchun ruxsat yo'q")
    order = ctx.db.scalar(select(Order).where(
        Order.id == oid, Order.company_id == ctx.cid
    ).with_for_update())
    if order is None:
        raise HTTPException(404, "Topilmadi")
    allowed = {"new": "preparing", "preparing": "ready", "ready": "done"}
    if allowed.get(order.status) != body.status:
        raise HTTPException(409, "Buyurtma holatini faqat keyingi bosqichga o'tkazish mumkin")
    order.status = body.status
    if body.status == "ready":
        order.ready_at = now_ms()
    ctx.db.commit()
    return order_out(order)


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
        "tickets": [ticket_out(t) for t in db.scalars(select(KitchenTicket).where(
            KitchenTicket.company_id == cid, KitchenTicket.created_at >= start_of_day_ms(), KitchenTicket.status != "done"
        ).order_by(KitchenTicket.id))],
        "checks": [check_out(c) for c in db.scalars(select(OpenCheck).where(
            OpenCheck.company_id == cid, OpenCheck.status == "open").order_by(OpenCheck.id))],
    }


@app.get("/api/reports/daily")
def daily_report(days: int = 7, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    days = max(1, min(days, 92))
    start = start_of_day_ms(days - 1)
    orders = ctx.db.scalars(select(Order).where(Order.company_id == ctx.cid, Order.created_at >= start)).all()
    out = []
    for d in range(days - 1, -1, -1):
        lo, hi = start_of_day_ms(d), start_of_day_ms(d - 1)
        day = [o for o in orders if lo <= o.created_at < hi and o.status != "cancelled"]
        out.append({"day": lo, "revenue": sum(o.total for o in day), "cost": sum(o.cost for o in day), "orders": len(day)})
    return out

# ---------- management financial snapshot ----------
@app.get("/api/reports/finance")
def finance_report(days: int = 30, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Cash-accounting approximation, not formal net profit or tax reporting."""
    days = max(1, min(days, 92))
    start = start_of_day_ms(days - 1)
    db, cid = ctx.db, ctx.cid
    orders = db.scalars(select(Order).where(
        Order.company_id == cid, Order.created_at >= start,
        Order.status != "cancelled",
    )).all()
    expenses = db.scalars(select(Expense).where(
        Expense.company_id == cid, Expense.created_at >= start,
    )).all()
    wages = db.scalars(select(StaffPayment).where(
        StaffPayment.company_id == cid, StaffPayment.created_at >= start,
    )).all()
    by_payment: dict[str, int] = {}
    for o in orders:
        by_payment[o.payment] = by_payment.get(o.payment, 0) + o.total

    daily = []
    for d in range(days - 1, -1, -1):
        lo, hi = start_of_day_ms(d), start_of_day_ms(d - 1)
        day_sales = [o for o in orders if lo <= o.created_at < hi]
        day_expenses = sum(e.amount for e in expenses if lo <= e.created_at < hi)
        day_wages = sum(w.amount for w in wages if lo <= w.created_at < hi)
        revenue = sum(o.total for o in day_sales)
        cogs = sum(o.cost for o in day_sales)
        daily.append({
            "day": lo, "orders": len(day_sales), "revenue": revenue,
            "cogs": cogs, "grossProfit": revenue - cogs,
            "expenses": day_expenses, "staffPayments": day_wages,
            "operatingBalance": revenue - cogs - day_expenses - day_wages,
        })
    def total(key: str) -> int:
        return sum(day[key] for day in daily)
    return {
        "days": days, "start": start,
        "orders": total("orders"), "revenue": total("revenue"),
        "cogs": total("cogs"), "grossProfit": total("grossProfit"),
        "expenses": total("expenses"), "staffPayments": total("staffPayments"),
        "operatingBalance": total("operatingBalance"),
        "byPayment": by_payment, "daily": daily,
        "note": "Tax, supplier debts, pending salaries and other liabilities are not included.",
    }


# ---------- platform owner (disabled until SUPERADMIN_KEY is configured) ----------
def require_superadmin(x_superadmin_key: str = Header(default="")) -> None:
    expected = os.environ.get("SUPERADMIN_KEY", "")
    if len(expected) < 40:
        raise HTTPException(503, "Superadmin sozlanmagan")
    if not secrets.compare_digest(x_superadmin_key, expected):
        raise HTTPException(401, "Superadmin ruxsati yo'q")


def platform_company(c: Company, subscription: Subscription | None) -> dict:
    return {
        "id": c.id, "slug": c.slug, "name": c.name, "createdAt": c.created_at,
        "subscription": None if subscription is None else {
            "plan": subscription.plan, "status": subscription.status,
            "expiresAt": subscription.expires_at, "updatedAt": subscription.updated_at
        }
    }


@app.get("/api/superadmin/companies")
def platform_companies(offset: int = 0, limit: int = 100, db: Session = Depends(get_db),
                       _: None = Depends(require_superadmin)) -> dict:
    offset, limit = max(0, offset), max(1, min(limit, 500))
    companies = db.scalars(select(Company).order_by(Company.id).offset(offset).limit(limit)).all()
    subscriptions = {p.company_id: p for p in db.scalars(
        select(Subscription).where(Subscription.company_id.in_([c.id for c in companies]))
    )} if companies else {}
    return {"items": [platform_company(c, subscriptions.get(c.id)) for c in companies],
            "offset": offset, "limit": limit}


class PlatformCompanyIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,40}$")
    name: str = Field(min_length=2, max_length=128)
    owner_name: str = Field(min_length=1, max_length=64)
    owner_pin: str = Field(pattern=r"^\d{4,6}$")
    plan: Literal["monthly", "yearly"] = "monthly"
    days: int = Field(default=30, ge=1, le=730)


@app.post("/api/superadmin/companies", status_code=201)
def platform_create_company(body: PlatformCompanyIn, db: Session = Depends(get_db),
                            _: None = Depends(require_superadmin)) -> dict:
    slug = body.slug.strip().lower()
    if db.scalar(select(Company).where(Company.slug == slug)):
        raise HTTPException(409, "Bunday login mavjud")
    company = create_company(db, slug, body.name.strip(), body.owner_name.strip(), body.owner_pin)
    expiry = now_ms() + body.days * 86400000
    sub = Subscription(company_id=company.id, plan=body.plan, status="active", expires_at=expiry)
    db.add(sub)
    db.commit()
    return platform_company(company, sub)


class PlatformSubscriptionIn(BaseModel):
    action: Literal["grant", "renew", "suspend"]
    plan: Literal["monthly", "yearly"] = "monthly"
    days: int = Field(default=30, ge=1, le=730)


@app.post("/api/superadmin/companies/{slug}/subscription")
def platform_subscription(slug: str, body: PlatformSubscriptionIn,
                          db: Session = Depends(get_db), _: None = Depends(require_superadmin)) -> dict:
    company = db.scalar(select(Company).where(Company.slug == slug))
    if company is None:
        raise HTTPException(404, "Qahvaxona topilmadi")
    sub = db.get(Subscription, company.id)
    if body.action == "suspend":
        if sub is None:
            raise HTTPException(409, "Obuna mavjud emas")
        sub.status, sub.updated_at = "suspended", now_ms()
    else:
        current = now_ms()
        base = max(current, sub.expires_at) if body.action == "renew" and sub is not None and sub.status == "active" else current
        expiry = base + body.days * 86400000
        if sub is None:
            sub = Subscription(company_id=company.id, plan=body.plan, status="active", expires_at=expiry)
            db.add(sub)
        else:
            sub.plan, sub.status, sub.expires_at, sub.updated_at = body.plan, "active", expiry, current
    db.commit()
    return platform_company(company, sub)


# ---------- promotions (aksiyalar) ----------

TIME_RE = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
DATE_RE = r"^([0-9]{4}-[0-9]{2}-[0-9]{2})?$"


def promotion_out(p: Promotion) -> dict:
    return {
        "id": p.id, "name": p.name, "pct": p.pct, "target": p.target, "keys": list(p.keys or []),
        "days": list(p.days or []), "startTime": p.start_time, "endTime": p.end_time,
        "dateFrom": p.date_from, "dateTo": p.date_to, "active": p.active,
    }


class PromotionIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    pct: int = Field(ge=1, le=90)
    target: Literal["all", "category", "product"] = "all"
    keys: list[str] = Field(default=[], max_length=200)
    days: list[int] = Field(default=[], max_length=7)
    startTime: str = Field(default="00:00", pattern=TIME_RE)
    endTime: str = Field(default="00:00", pattern=TIME_RE)
    dateFrom: str = Field(default="", pattern=DATE_RE)
    dateTo: str = Field(default="", pattern=DATE_RE)
    active: bool = True


def apply_promotion_body(ctx: Ctx, p: Promotion, body: PromotionIn) -> None:
    if any(d < 0 or d > 6 for d in body.days) or len(set(body.days)) != len(body.days):
        raise HTTPException(422, "Hafta kunlari noto'g'ri")
    if body.dateFrom and body.dateTo and body.dateTo < body.dateFrom:
        raise HTTPException(422, "Sana oralig'i noto'g'ri")
    keys = list(dict.fromkeys(body.keys))
    if body.target == "all":
        keys = []
    else:
        if not keys:
            raise HTTPException(422, "Aksiya uchun kategoriya yoki mahsulot tanlang")
        model = Category if body.target == "category" else Product
        known = {r.key for r in rows(ctx.db, model, ctx.cid)}
        if any(k not in known for k in keys):
            raise HTTPException(422, "Aksiyada noma'lum kategoriya yoki mahsulot")
    p.name, p.pct, p.target, p.keys = body.name.strip(), body.pct, body.target, keys
    p.days = sorted(body.days)
    p.start_time, p.end_time = body.startTime, body.endTime
    p.date_from, p.date_to, p.active = body.dateFrom, body.dateTo, body.active


def get_owned(ctx: Ctx, model, row_id: int):
    row = ctx.db.get(model, row_id)
    if row is None or row.company_id != ctx.cid:
        raise HTTPException(404, "Topilmadi")
    return row


@app.get("/api/promotions")
def promotions_list(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    return [promotion_out(p) for p in rows(ctx.db, Promotion, ctx.cid)]


@app.post("/api/promotions")
def promotions_add(body: PromotionIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    p = Promotion(company_id=ctx.cid)
    apply_promotion_body(ctx, p, body)
    ctx.db.add(p)
    ctx.db.commit()
    return promotion_out(p)


@app.put("/api/promotions/{pid}")
def promotions_update(pid: int, body: PromotionIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    p = get_owned(ctx, Promotion, pid)
    apply_promotion_body(ctx, p, body)
    ctx.db.commit()
    return promotion_out(p)


@app.delete("/api/promotions/{pid}")
def promotions_delete(pid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    ctx.db.delete(get_owned(ctx, Promotion, pid))
    ctx.db.commit()
    return {"ok": True}


# ---------- sales analytics: ABC, breakdowns, risky receipts ----------

def parse_range(date_from: str | None, date_to: str | None, days: int) -> tuple[int, int]:
    if date_from is None and date_to is None:
        days = max(1, min(days, 366))
        return start_of_day_ms(days - 1), start_of_day_ms(-1)
    if not date_from or not date_to:
        raise HTTPException(400, "Ikkala sanani kiriting")
    try:
        lo = datetime.strptime(date_from, "%Y-%m-%d")
        hi = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Sana formati noto'g'ri")
    if hi < lo or (hi - lo).days > 366:
        raise HTTPException(400, "Sana oralig'i 1-366 kun bo'lishi kerak")
    return int(lo.replace(tzinfo=TZ).timestamp() * 1000), int((hi + timedelta(days=1)).replace(tzinfo=TZ).timestamp() * 1000)


def orders_between(ctx: Ctx, since: int, until: int) -> list[Order]:
    return ctx.db.scalars(select(Order).where(
        Order.company_id == ctx.cid, Order.created_at >= since, Order.created_at < until
    ).order_by(Order.created_at)).all()


def abc_classes(rows_: list[dict], key: str = "revenue") -> None:
    total = sum(r[key] for r in rows_) or 1
    acc = 0
    for r in sorted(rows_, key=lambda r: r[key], reverse=True):
        r["share"] = round(r[key] * 100 / total, 1)
        r["abc"] = "A" if acc < total * 0.8 else ("B" if acc < total * 0.95 else "C")
        acc += r[key]


@app.get("/api/reports/sales")
def sales_report(days: int = 30, date_from: str | None = None, date_to: str | None = None,
                 ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Net revenue by product, category, staff, payment and hour, plus ABC classes."""
    since, until = parse_range(date_from, date_to, days)
    prods = {p.key: p for p in rows(ctx.db, Product, ctx.cid)}
    cat_names = {c.key: c.name for c in rows(ctx.db, Category, ctx.cid)}
    by_product: dict[str, dict] = {}
    by_cat: dict[str, dict] = {}
    by_staff: dict[str, dict] = {}
    by_payment: dict[str, int] = {}
    hours = [{"hour": h, "orders": 0, "revenue": 0} for h in range(24)]
    revenue = cost = count = cancelled = discount = 0
    for o in orders_between(ctx, since, until):
        staff = by_staff.setdefault(o.staff_name, {"name": o.staff_name, "orders": 0, "revenue": 0, "cancelled": 0, "discount": 0})
        if o.status == "cancelled":
            staff["cancelled"] += 1
            cancelled += 1
            continue
        count += 1
        revenue += o.total
        cost += o.cost
        discount += o.discount
        staff["orders"] += 1
        staff["revenue"] += o.total
        staff["discount"] += o.discount
        by_payment[o.payment] = by_payment.get(o.payment, 0) + o.total
        hour = datetime.fromtimestamp(o.created_at / 1000, TZ).hour
        hours[hour]["orders"] += 1
        hours[hour]["revenue"] += o.total
        ratio = o.total / o.subtotal if o.subtotal else 0
        for it in o.items:
            pid = it.get("productId", "")
            net = round(it["unitPrice"] * it["qty"] * ratio)
            item_cost = it.get("unitCost", 0) * it["qty"]
            p = prods.get(pid)
            row = by_product.setdefault(pid, {"id": pid, "name": p.name if p else it.get("name", pid),
                                              "cat": p.cat if p else "", "qty": 0, "revenue": 0, "cost": 0})
            row["qty"] += it["qty"]
            row["revenue"] += net
            row["cost"] += item_cost
            cat = row["cat"]
            crow = by_cat.setdefault(cat, {"id": cat, "name": cat_names.get(cat, "—"), "qty": 0, "revenue": 0, "cost": 0})
            crow["qty"] += it["qty"]
            crow["revenue"] += net
            crow["cost"] += item_cost
    products = list(by_product.values())
    for r in products + list(by_cat.values()):
        r["profit"] = r["revenue"] - r["cost"]
    abc_classes(products)
    for st in by_staff.values():
        st["avg"] = round(st["revenue"] / st["orders"]) if st["orders"] else 0
    return {
        "from": since, "to": until,
        "totals": {"orders": count, "revenue": revenue, "cost": cost, "profit": revenue - cost,
                   "avg": round(revenue / count) if count else 0, "cancelled": cancelled, "discount": discount},
        "products": sorted(products, key=lambda r: r["revenue"], reverse=True),
        "categories": sorted(by_cat.values(), key=lambda r: r["revenue"], reverse=True),
        "staff": sorted(by_staff.values(), key=lambda r: r["revenue"], reverse=True),
        "payments": by_payment,
        "hours": hours,
    }


RISK_DISCOUNT_PCT = 20
RISK_LATE_CANCEL_MS = 15 * 60 * 1000


@app.get("/api/reports/risky")
def risky_report(days: int = 30, date_from: str | None = None, date_to: str | None = None,
                 ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Receipts worth a second look: cancellations, large manual discounts, zero totals."""
    since, until = parse_range(date_from, date_to, days)
    out = []
    per_staff: dict[str, dict] = {}
    for o in orders_between(ctx, since, until):
        flags = []
        promo = sum(it.get("promoDiscount", 0) for it in o.items)
        manual = max(0, o.discount - promo)
        if o.status == "cancelled":
            flags.append("cancelled")
            if o.cancelled_at and o.cancelled_at - o.created_at > RISK_LATE_CANCEL_MS:
                flags.append("late_cancel")
            if o.cancelled_by and o.cancelled_by == o.staff_name:
                flags.append("self_cancel")
        if o.subtotal and manual * 100 >= o.subtotal * RISK_DISCOUNT_PCT:
            flags.append("big_discount")
        if o.total == 0 and o.status != "cancelled":
            flags.append("zero_total")
        if o.bonus_used and o.subtotal and o.bonus_used * 100 >= o.subtotal * 50:
            flags.append("big_bonus")
        if not flags:
            continue
        rec = order_out(o)
        rec["flags"] = flags
        rec["manualDiscount"] = manual
        out.append(rec)
        st = per_staff.setdefault(o.staff_name, {"name": o.staff_name, "receipts": 0, "amount": 0})
        st["receipts"] += 1
        st["amount"] += o.subtotal
    out.sort(key=lambda r: r["createdAt"], reverse=True)
    return {"from": since, "to": until, "receipts": out[:1000],
            "staff": sorted(per_staff.values(), key=lambda r: r["receipts"], reverse=True)}


# ---------- staff checklists ----------

def checklist_out(c: ChecklistTemplate) -> dict:
    return {"id": c.id, "name": c.name, "kind": c.kind, "items": list(c.items or []), "active": c.active}


class ChecklistIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: Literal["open", "close", "any"] = "any"
    items: list[str] = Field(min_length=1, max_length=40)
    active: bool = True


def clean_items(items: list[str]) -> list[str]:
    cleaned = [i.strip()[:120] for i in items if i.strip()]
    if not cleaned:
        raise HTTPException(422, "Kamida bitta band yozing")
    return cleaned


@app.get("/api/checklists")
def checklists_list(ctx: Ctx = Depends(auth)) -> list[dict]:
    items = rows(ctx.db, ChecklistTemplate, ctx.cid)
    if ctx.staff.role not in MANAGERS:
        items = [c for c in items if c.active]
    return [checklist_out(c) for c in items]


@app.post("/api/checklists")
def checklists_add(body: ChecklistIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    c = ChecklistTemplate(company_id=ctx.cid, name=body.name.strip(), kind=body.kind,
                          items=clean_items(body.items), active=body.active)
    ctx.db.add(c)
    ctx.db.commit()
    return checklist_out(c)


@app.put("/api/checklists/{cid_}")
def checklists_update(cid_: int, body: ChecklistIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    c = get_owned(ctx, ChecklistTemplate, cid_)
    c.name, c.kind, c.items, c.active = body.name.strip(), body.kind, clean_items(body.items), body.active
    ctx.db.commit()
    return checklist_out(c)


@app.delete("/api/checklists/{cid_}")
def checklists_delete(cid_: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    ctx.db.delete(get_owned(ctx, ChecklistTemplate, cid_))
    ctx.db.commit()
    return {"ok": True}


class ChecklistRunIn(BaseModel):
    done: list[bool] = Field(max_length=40)


def checklist_run_out(r: ChecklistRun) -> dict:
    return {"id": r.id, "templateId": r.template_id, "name": r.template_name, "shiftId": r.shift_id,
            "staff": r.staff_name, "items": r.items, "done": r.done, "total": r.total, "createdAt": r.created_at}


@app.post("/api/checklists/{cid_}/runs")
def checklists_submit(cid_: int, body: ChecklistRunIn, ctx: Ctx = Depends(auth)) -> dict:
    c = get_owned(ctx, ChecklistTemplate, cid_)
    if not c.active:
        raise HTTPException(409, "Checklist o'chirilgan")
    if len(body.done) != len(c.items):
        raise HTTPException(422, "Checklist bandlari soni mos emas")
    shift = open_shift(ctx.db, ctx.cid)
    lines = [{"text": text, "done": bool(d)} for text, d in zip(c.items, body.done)]
    r = ChecklistRun(company_id=ctx.cid, template_id=c.id, template_name=c.name,
                     shift_id=shift.id if shift else None, staff_name=ctx.staff.name,
                     items=lines, done=sum(body.done), total=len(lines))
    ctx.db.add(r)
    ctx.db.commit()
    return checklist_run_out(r)


@app.get("/api/checklist-runs")
def checklist_runs(days: int = 30, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = (select(ChecklistRun).where(ChecklistRun.company_id == ctx.cid,
                                    ChecklistRun.created_at >= start_of_day_ms(max(1, min(days, 366))))
         .order_by(ChecklistRun.id.desc()).limit(500))
    return [checklist_run_out(r) for r in ctx.db.scalars(q)]


# ---------- recurring payments (ijara, kommunal) ----------

def current_month() -> str:
    return datetime.now(TZ).strftime("%Y-%m")


def recurring_out(r: RecurringPayment) -> dict:
    today = datetime.now(TZ)
    paid = r.last_paid_month >= today.strftime("%Y-%m") if r.last_paid_month else False
    return {
        "id": r.id, "name": r.name, "amount": r.amount, "category": r.category, "payment": r.payment,
        "day": r.day, "active": r.active, "lastPaidMonth": r.last_paid_month,
        "paidThisMonth": paid, "due": r.active and not paid and today.day >= r.day,
    }


class RecurringIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0, le=10_000_000_000)
    category: str = Field(min_length=1, max_length=64)
    payment: Literal["cash", "card", "bank"] = "bank"
    day: int = Field(ge=1, le=28)
    active: bool = True


@app.get("/api/recurring")
def recurring_list(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    return [recurring_out(r) for r in rows(ctx.db, RecurringPayment, ctx.cid)]


@app.post("/api/recurring")
def recurring_add(body: RecurringIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    r = RecurringPayment(company_id=ctx.cid, name=body.name.strip(), amount=body.amount,
                         category=body.category.strip(), payment=body.payment, day=body.day,
                         active=body.active, last_paid_month="")
    ctx.db.add(r)
    ctx.db.commit()
    return recurring_out(r)


@app.put("/api/recurring/{rid}")
def recurring_update(rid: int, body: RecurringIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    r = get_owned(ctx, RecurringPayment, rid)
    r.name, r.amount, r.category = body.name.strip(), body.amount, body.category.strip()
    r.payment, r.day, r.active = body.payment, body.day, body.active
    ctx.db.commit()
    return recurring_out(r)


@app.delete("/api/recurring/{rid}")
def recurring_delete(rid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    ctx.db.delete(get_owned(ctx, RecurringPayment, rid))
    ctx.db.commit()
    return {"ok": True}


class RecurringPayIn(BaseModel):
    month: str | None = Field(default=None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    amount: int | None = Field(default=None, gt=0, le=10_000_000_000)


@app.post("/api/recurring/{rid}/pay")
def recurring_pay(rid: int, body: RecurringPayIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Record this month's payment once as an Expense."""
    r = ctx.db.scalar(select(RecurringPayment).where(
        RecurringPayment.id == rid, RecurringPayment.company_id == ctx.cid).with_for_update())
    if r is None:
        raise HTTPException(404, "Topilmadi")
    month = body.month or current_month()
    if r.last_paid_month and r.last_paid_month >= month:
        raise HTTPException(409, "Bu oy uchun allaqachon to'langan")
    ctx.db.add(Expense(company_id=ctx.cid, amount=body.amount or r.amount, category=r.category,
                       description=f"{r.name} ({month})"[:256], payment=r.payment, staff_name=ctx.staff.name))
    r.last_paid_month = month
    ctx.db.commit()
    return recurring_out(r)


# ---------- restaurant mode: workshops, halls, tables, open checks, kitchen tickets ----------

class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


@app.post("/api/workshops")
def workshop_add(body: NameIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    w = Workshop(company_id=ctx.cid, key=slugify(body.name), name=body.name.strip(), sort=len(rows(ctx.db, Workshop, ctx.cid)))
    ctx.db.add(w)
    ctx.db.commit()
    return {"id": w.key, "name": w.name}


@app.put("/api/workshops/{key}")
def workshop_rename(key: str, body: NameIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    w = get_row(ctx.db, Workshop, ctx.cid, key)
    w.name = body.name.strip()
    ctx.db.commit()
    return {"id": w.key, "name": w.name}


@app.delete("/api/workshops/{key}")
def workshop_delete(key: str, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    w = get_row(ctx.db, Workshop, ctx.cid, key)
    for c in rows(ctx.db, Category, ctx.cid):
        if c.workshop == key:
            c.workshop = ""
    ctx.db.delete(w)
    ctx.db.commit()
    return {"ok": True}


class CategoryWorkshopIn(BaseModel):
    workshop: str = Field(default="", max_length=64)


@app.patch("/api/categories/{key}/workshop")
def category_workshop(key: str, body: CategoryWorkshopIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    cat = get_row(ctx.db, Category, ctx.cid, key)
    if body.workshop:
        get_row(ctx.db, Workshop, ctx.cid, body.workshop)
    cat.workshop = body.workshop
    ctx.db.commit()
    return {"id": cat.key, "name": cat.name, "workshop": cat.workshop}


def hall_out(h: Hall, tables: list[DiningTable]) -> dict:
    return {"id": h.id, "name": h.name, "tables": [
        {"id": t.id, "name": t.name, "seats": t.seats, "active": t.active}
        for t in sorted((t for t in tables if t.hall_id == h.id), key=lambda t: (t.sort, t.id))]}


@app.get("/api/halls")
def halls_list(ctx: Ctx = Depends(auth)) -> list[dict]:
    tables = rows(ctx.db, DiningTable, ctx.cid)
    return [hall_out(h, tables) for h in sorted(rows(ctx.db, Hall, ctx.cid), key=lambda h: (h.sort, h.id))]


@app.post("/api/halls")
def hall_add(body: NameIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    h = Hall(company_id=ctx.cid, name=body.name.strip(), sort=len(rows(ctx.db, Hall, ctx.cid)))
    ctx.db.add(h)
    ctx.db.commit()
    return hall_out(h, [])


@app.put("/api/halls/{hid}")
def hall_rename(hid: int, body: NameIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    h = get_owned(ctx, Hall, hid)
    h.name = body.name.strip()
    ctx.db.commit()
    return hall_out(h, rows(ctx.db, DiningTable, ctx.cid))


@app.delete("/api/halls/{hid}")
def hall_delete(hid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    h = get_owned(ctx, Hall, hid)
    if any(t.hall_id == h.id for t in rows(ctx.db, DiningTable, ctx.cid)):
        raise HTTPException(409, "Avval zaldagi stollarni o'chiring")
    ctx.db.delete(h)
    ctx.db.commit()
    return {"ok": True}


class TableIn(BaseModel):
    hallId: int
    name: str = Field(min_length=1, max_length=32)
    seats: int = Field(default=4, ge=1, le=100)
    active: bool = True


@app.post("/api/tables")
def table_add(body: TableIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    get_owned(ctx, Hall, body.hallId)
    t = DiningTable(company_id=ctx.cid, hall_id=body.hallId, name=body.name.strip(), seats=body.seats,
                    active=body.active, sort=len(rows(ctx.db, DiningTable, ctx.cid)))
    ctx.db.add(t)
    ctx.db.commit()
    return {"id": t.id, "name": t.name, "seats": t.seats, "active": t.active, "hallId": t.hall_id}


@app.put("/api/tables/{tid}")
def table_update(tid: int, body: TableIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    t = get_owned(ctx, DiningTable, tid)
    get_owned(ctx, Hall, body.hallId)
    t.hall_id, t.name, t.seats, t.active = body.hallId, body.name.strip(), body.seats, body.active
    ctx.db.commit()
    return {"id": t.id, "name": t.name, "seats": t.seats, "active": t.active, "hallId": t.hall_id}


@app.delete("/api/tables/{tid}")
def table_delete(tid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    t = get_owned(ctx, DiningTable, tid)
    if ctx.db.scalar(select(OpenCheck).where(OpenCheck.company_id == ctx.cid, OpenCheck.table_id == t.id,
                                             OpenCheck.status == "open")):
        raise HTTPException(409, "Stolda ochiq hisob bor")
    ctx.db.delete(t)
    ctx.db.commit()
    return {"ok": True}


def check_total(c: OpenCheck) -> int:
    return sum(i["unitPrice"] * i["qty"] for i in (c.items or []))


def check_out(c: OpenCheck) -> dict:
    return {
        "id": c.id, "tableId": c.table_id, "tableName": c.table_name, "guests": c.guests,
        "waiter": c.waiter_name, "comment": c.comment, "items": c.items or [], "total": check_total(c),
        "status": c.status, "orderId": str(c.order_id) if c.order_id else None,
        "createdAt": c.created_at, "updatedAt": c.updated_at, "closedAt": c.closed_at,
        "unsent": sum(max(0, i["qty"] - i.get("sent", 0)) for i in (c.items or [])),
    }


def ticket_out(t: KitchenTicket) -> dict:
    return {"id": t.id, "checkId": t.check_id, "workshop": t.workshop, "tableName": t.table_name,
            "waiter": t.waiter_name, "items": t.items, "comment": t.comment, "status": t.status,
            "createdAt": t.created_at, "readyAt": t.ready_at}


def get_check(ctx: Ctx, check_id: int, lock: bool = True) -> OpenCheck:
    q = select(OpenCheck).where(OpenCheck.id == check_id, OpenCheck.company_id == ctx.cid)
    c = ctx.db.scalar(q.with_for_update() if lock else q)
    if c is None:
        raise HTTPException(404, "Hisob topilmadi")
    return c


def require_open(c: OpenCheck) -> None:
    if c.status != "open":
        raise HTTPException(409, "Hisob yopilgan")


def can_void(ctx: Ctx) -> bool:
    return ctx.staff.role in MANAGERS or bool(ctx.staff.can_cancel_orders)


class CheckOpenIn(BaseModel):
    tableId: int | None = None
    guests: int = Field(default=1, ge=1, le=100)
    comment: str = Field(default="", max_length=200)


def table_label(ctx: Ctx, table_id: int | None) -> str:
    if table_id is None:
        return ""
    t = get_owned(ctx, DiningTable, table_id)
    if not t.active:
        raise HTTPException(409, "Stol faol emas")
    hall = ctx.db.get(Hall, t.hall_id)
    return (f"{hall.name} · {t.name}" if hall else t.name)[:64]


@app.get("/api/checks")
def checks_list(ctx: Ctx = Depends(require(*WAITERS))) -> list[dict]:
    q = select(OpenCheck).where(OpenCheck.company_id == ctx.cid, OpenCheck.status == "open").order_by(OpenCheck.id)
    return [check_out(c) for c in ctx.db.scalars(q)]


@app.post("/api/checks")
def check_open(body: CheckOpenIn, ctx: Ctx = Depends(require(*WAITERS))) -> dict:
    shift = open_shift(ctx.db, ctx.cid)
    if shift is None:
        raise HTTPException(409, "Avval smenani oching")
    c = OpenCheck(company_id=ctx.cid, shift_id=shift.id, table_id=body.tableId, table_name=table_label(ctx, body.tableId),
                  guests=body.guests, waiter_name=ctx.staff.name, comment=body.comment.strip(), items=[])
    ctx.db.add(c)
    ctx.db.commit()
    return check_out(c)


@app.patch("/api/checks/{check_id}")
def check_update(check_id: int, body: CheckOpenIn, ctx: Ctx = Depends(require(*WAITERS))) -> dict:
    """Move the bill to another table, change guests or the comment."""
    c = get_check(ctx, check_id)
    require_open(c)
    c.table_id, c.table_name = body.tableId, table_label(ctx, body.tableId)
    c.guests, c.comment, c.updated_at = body.guests, body.comment.strip(), now_ms()
    ctx.db.commit()
    return check_out(c)


class CheckItemsIn(BaseModel):
    items: list[OrderItemIn] = Field(max_length=100)


@app.put("/api/checks/{check_id}/items")
def check_set_items(check_id: int, body: CheckItemsIn, ctx: Ctx = Depends(require(*WAITERS))) -> dict:
    """Replace the bill's lines. Lines already sent to the kitchen can only be reduced with cancel rights."""
    db, cid = ctx.db, ctx.cid
    c = get_check(ctx, check_id)
    require_open(c)
    prods = {p.key: p for p in rows(db, Product, cid)}
    mods = {m.key: m for m in rows(db, Modifier, cid)}
    ings = {i.key: i for i in rows(db, Ingredient, cid)}
    sent_before = {i["key"]: i.get("sent", 0) for i in (c.items or [])}
    items: list[dict] = []
    for it in body.items:
        product = prods.get(it.productId)
        if not product:
            raise HTTPException(400, "Mahsulot topilmadi")
        built = build_item(product, it.size, it.modIds, it.qty, mods, ings)
        same = next((x for x in items if x["key"] == built["key"]), None)
        if same:
            same["qty"] += built["qty"]
            if same["qty"] > 99:
                raise HTTPException(400, "Miqdor noto'g'ri")
        else:
            items.append(built)
    for key, sent in sent_before.items():
        line = next((x for x in items if x["key"] == key), None)
        qty = line["qty"] if line else 0
        if qty < sent and not can_void(ctx):
            raise HTTPException(403, "Oshxonaga yuborilgan taomni kamaytirish uchun ruxsat yo'q")
        if line:
            line["sent"] = min(sent, qty)
    for line in items:
        line.setdefault("sent", 0)
    if stock_settings(db, cid).auto_stoplist:
        need: dict[str, float] = {}
        for it in items:
            for l in it["consumption"]:
                need[l["ing"]] = need.get(l["ing"], 0) + l["qty"] * it["qty"]
        short = [ings[k].name for k, q in need.items() if k in ings and ings[k].stock + 0.000001 < q]
        if short:
            raise HTTPException(409, f"Qoldiq yetarli emas (stop-list): {', '.join(short)}")
    c.items, c.updated_at = items, now_ms()
    db.commit()
    return check_out(c)


def send_to_kitchen(ctx: Ctx, c: OpenCheck) -> list[KitchenTicket]:
    """Create one ticket per workshop for quantities not yet sent; mark them sent."""
    prods = {p.key: p for p in rows(ctx.db, Product, ctx.cid)}
    cats = {cat.key: cat for cat in rows(ctx.db, Category, ctx.cid)}
    groups: dict[str, list[dict]] = {}
    items = [dict(i) for i in (c.items or [])]
    for line in items:
        delta = line["qty"] - line.get("sent", 0)
        if delta <= 0:
            continue
        product = prods.get(line["productId"])
        cat = cats.get(product.cat) if product else None
        workshop = cat.workshop if cat else ""
        groups.setdefault(workshop or "", []).append(
            {"name": line["name"], "size": line["size"], "mods": line["mods"], "qty": delta})
        line["sent"] = line["qty"]
    tickets = []
    for workshop, lines in groups.items():
        t = KitchenTicket(company_id=ctx.cid, check_id=c.id, workshop=workshop, table_name=c.table_name,
                          waiter_name=c.waiter_name, items=lines, comment=c.comment)
        ctx.db.add(t)
        tickets.append(t)
    c.items = items
    c.updated_at = now_ms()
    return tickets


@app.post("/api/checks/{check_id}/send")
def check_send(check_id: int, ctx: Ctx = Depends(require(*WAITERS))) -> dict:
    c = get_check(ctx, check_id)
    require_open(c)
    tickets = send_to_kitchen(ctx, c)
    if not tickets:
        raise HTTPException(409, "Yuboriladigan yangi taom yo'q")
    ctx.db.commit()
    return {"check": check_out(c), "tickets": [ticket_out(t) for t in tickets]}


class CheckPayIn(BaseModel):
    payment: Literal["naqd", "karta", "payme", "click"]
    cashGiven: int | None = Field(default=None, ge=0)
    discountPct: int = Field(default=0, ge=0, le=50)
    customerPhone: str = Field(default="", max_length=20)
    bonusRedeem: int = Field(default=0, ge=0)
    clientKey: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{12,64}$")


@app.post("/api/checks/{check_id}/pay")
def check_pay(check_id: int, body: CheckPayIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    """Close the bill as a paid order. Unsent items are sent to the kitchen first."""
    c = get_check(ctx, check_id)
    if c.status == "paid" and c.order_id:
        existing = ctx.db.get(Order, c.order_id)
        if existing is not None:
            return order_out(existing)
    require_open(c)
    if not c.items:
        raise HTTPException(409, "Hisob bo'sh")
    send_to_kitchen(ctx, c)
    order_in = OrderIn(
        items=[OrderItemIn(productId=i["productId"], size=i["key"].split("|")[1], modIds=i["modIds"], qty=i["qty"]) for i in c.items],
        customer=c.table_name[:64], discountPct=body.discountPct, payment=body.payment, cashGiven=body.cashGiven,
        customerPhone=body.customerPhone, bonusRedeem=body.bonusRedeem, clientKey=body.clientKey,
    )

    def mark_paid(order: Order) -> None:
        c.status, c.order_id, c.closed_at = "paid", order.id, now_ms()

    return place_order(order_in, ctx, status="done", stock_guard=False, on_created=mark_paid)


class VoidIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


@app.post("/api/checks/{check_id}/void")
def check_void(check_id: int, body: VoidIn, ctx: Ctx = Depends(require(*WAITERS))) -> dict:
    c = get_check(ctx, check_id)
    require_open(c)
    if any(i.get("sent", 0) > 0 for i in (c.items or [])) and not can_void(ctx):
        raise HTTPException(403, "Oshxonaga yuborilgan hisobni bekor qilish uchun ruxsat yo'q")
    c.status, c.void_reason, c.closed_at = "void", f"{ctx.staff.name}: {body.reason.strip()}"[:200], now_ms()
    ctx.db.commit()
    return check_out(c)


class TicketStatusIn(BaseModel):
    status: Literal["preparing", "ready", "done"]


@app.patch("/api/tickets/{ticket_id}")
def ticket_status(ticket_id: int, body: TicketStatusIn, ctx: Ctx = Depends(auth)) -> dict:
    if ctx.staff.role not in BARISTAS and not (ctx.staff.role == "kassir" and ctx.staff.can_barista) \
            and ctx.staff.role != "ofitsiant":
        raise HTTPException(403, "Barista vazifasi uchun ruxsat yo'q")
    t = ctx.db.scalar(select(KitchenTicket).where(KitchenTicket.id == ticket_id,
                                                  KitchenTicket.company_id == ctx.cid).with_for_update())
    if t is None:
        raise HTTPException(404, "Topilmadi")
    allowed = {"new": "preparing", "preparing": "ready", "ready": "done"}
    if allowed.get(t.status) != body.status:
        raise HTTPException(409, "Buyurtma holatini faqat keyingi bosqichga o'tkazish mumkin")
    if ctx.staff.role == "ofitsiant" and body.status != "done":
        raise HTTPException(403, "Ofitsiant faqat tayyor taomni olib ketganini belgilaydi")
    t.status = body.status
    if body.status == "ready":
        t.ready_at = now_ms()
    ctx.db.commit()
    return ticket_out(t)
