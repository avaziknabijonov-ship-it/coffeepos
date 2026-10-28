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
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .access_logs import install_receipt_access_filter
from .images import router as images_router, validate_image_url
from .combos import resolve_combo
from .promotions import capped_discount, choose_promotion, discount_amount
from . import seed
from .audit import install_guards, record as audit_record
from .db import (
    Base, Branch, BranchStock, OrderPayment, BonusConfig, BonusLedger, Category, Company, Customer, Expense, StaffPayment, Ingredient, Inventory, Modifier, Order, Product, PurchaseInvoice, Subscription, PayrollPlan, SessionLocal, Shift, Staff, StockMove, DraftOrder, OrderRefund, AuditEvent, Promotion, ReceiptLink, engine, now_ms, DiningTable, OfflineConflict,
)
from .receipts import make_receipt_token, read_receipt_token, receipt_html, TTL as RECEIPT_TTL
from .payment_rules import PaymentPart, validate_refund, validate_split_payment
from .logic import build_item
from .security import LoginLimiter, check_pin, hash_pin, make_token, read_token
from . import migrations
from .branches import router as branches_router
from .tables import router as tables_router, validate_table
from .devices import router as devices_router
from .integrations import fiscalize, router as integrations_router, sale_receipt
from .inventory_ops import refresh_low_stock, router as inventory_router
from . import stock as branch_stock
from .core import (
    enabled_modules, BARISTAS, CASHIERS, MANAGERS, TZ, Ctx, Role, auth, get_db, get_row, open_shift, require, rows,
    start_of_day_ms,
)

def migrate() -> None:
    """Additive legacy column upgrades (kept for callers predating versioned migrations)."""
    migrations.legacy_columns(engine)


def init_db() -> None:
    Base.metadata.create_all(engine)
    migrations.run(engine)
    install_guards(engine)
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
    install_receipt_access_filter()
    init_db()
    yield


app = FastAPI(title="CoffeePOS API", lifespan=lifespan)
app.include_router(images_router)
app.include_router(branches_router)
app.include_router(inventory_router)
app.include_router(tables_router)
app.include_router(devices_router)
app.include_router(integrations_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
limiter = LoginLimiter()


# ---------- serializers ----------

def staff_out(s: Staff) -> dict:
    return {"id": s.id, "name": s.name, "role": s.role, "active": s.active, "canBarista": bool(s.can_barista), "canCancelOrders": bool(s.can_cancel_orders), "canReprintReceipts": bool(s.can_reprint_receipts), "branchId": s.branch_id}


def order_payment_parts(order: Order) -> list[dict]:
    """Collected tenders; legacy orders remain readable as one full-amount tender."""
    if order.payment_parts is None:
        return [{"method": order.payment, "amount": order.total}]
    return order.payment_parts


def add_payment_totals(by_payment: dict[str, int], order: Order) -> None:
    for part in order_payment_parts(order):
        by_payment[part["method"]] = by_payment.get(part["method"], 0) + part["amount"]


def order_out(o: Order) -> dict:
    return {
        "note": o.note, "guestCount": o.guest_count, "waiter": o.waiter_name, "id": str(o.id), "number": o.number, "customer": o.customer, "items": o.items,
        "subtotal": o.subtotal, "discount": o.discount, "total": o.total, "cost": o.cost,
        "payment": o.payment, "paymentParts": order_payment_parts(o), "cashGiven": o.cash_given, "status": o.status,
        "promotion": o.promotion_snapshot, "bonusUsed": o.bonus_used, "bonusEarned": o.bonus_earned,
        "cancelledAt": o.cancelled_at, "cancelledBy": o.cancelled_by, "cancelReason": o.cancel_reason,
        "createdAt": o.created_at, "readyAt": o.ready_at, "barista": o.staff_name, "shiftId": o.shift_id,
        "paymentStatus": o.payment_status or "paid", "paid": sum(p["amount"] for p in order_payment_parts(o)),
        "outstanding": o.total - sum(p["amount"] for p in order_payment_parts(o)) if o.payment_status == "partial" else 0,
        "branchId": o.branch_id, "staffId": o.staff_id, "service": o.service, "table": o.table_name,
        "fiscalStatus": o.fiscal_status or "nonfiscal",
    }


def ingredient_out(i: Ingredient) -> dict:
    return {"id": i.key, "name": i.name, "unit": i.unit, "cost": i.cost, "stock": i.stock, "min": i.min}


def product_out(p: Product) -> dict:
    return {"id": p.key, "cat": p.cat, "name": p.name, "comboComponents": p.combo_components, "imageUrl": p.image_url, "mods": p.mods, "sizes": p.sizes, "active": p.active}


def shift_out(s: Shift | None) -> dict | None:
    if not s:
        return None
    return {
        "id": s.id, "staff": s.staff_name, "openedAt": s.opened_at, "openingCash": s.opening_cash,
        "closedAt": s.closed_at, "closingCash": s.closing_cash, "expectedCash": s.expected_cash,
        "closedBy": s.closed_by, "branchId": s.branch_id,
        "difference": None if s.closing_cash is None or s.expected_cash is None else s.closing_cash - s.expected_cash,
    }


# ---------- helpers ----------

def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return f"{base or 'item'}-{secrets.token_hex(2)}"


def pin_taken(db: Session, cid: int, pin: str, exclude: int | None = None) -> bool:
    for s in rows(db, Staff, cid):
        if s.id != exclude and s.active and check_pin(pin, s.pin_hash):
            return True
    return False


def create_company(db: Session, slug: str, name: str, owner_name: str, owner_pin: str, profile: str = "coffee") -> Company:
    company = Company(slug=slug, name=name)
    db.add(company)
    db.flush()
    cid = company.id
    db.add(Branch(company_id=cid, name="Asosiy filial", is_default=True))
    db.add(Staff(company_id=cid, name=owner_name, role="owner", pin_hash=hash_pin(owner_pin)))
    if profile == "hookah":
        for i, (key, name) in enumerate([("hookah", "Kalyan"), ("tea", "Choy"), ("cold", "Sovuq ichimliklar"), ("snacks", "Sneklar")]):
            db.add(Category(company_id=cid, key=key, name=name, sort=i))
        return company
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
        "company": {"slug": company.slug, "name": company.name, "modules": enabled_modules(db, company.id)},
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
    return {"staff": staff_out(ctx.staff), "company": {"slug": ctx.company.slug, "name": ctx.company.name, "modules": enabled_modules(ctx.db, ctx.cid)},
            "branch": {"id": ctx.branch.id, "name": ctx.branch.name} if ctx.branch else None}


# ---------- menu ----------

@app.get("/api/menu")
def menu(ctx: Ctx = Depends(auth)) -> dict:
    db, cid = ctx.db, ctx.cid
    cats = sorted(rows(db, Category, cid), key=lambda c: (c.sort, c.id))
    prods = sorted(rows(db, Product, cid), key=lambda p: (p.sort, p.id))
    mods = sorted(rows(db, Modifier, cid), key=lambda m: (m.sort, m.id))
    product_map = {p.key: p for p in prods}
    ingredient_map = {i.key: i for i in rows(db, Ingredient, cid)}
    modifier_map = {m.key: m for m in mods}
    products_out = []
    for product in prods:
        entry = product_out(product)
        if product.combo_components:
            try:
                resolved = resolve_combo(product, product_map, modifier_map, ingredient_map)
                entry["sizes"] = resolved.sizes
            except HTTPException:
                entry["active"] = False
        products_out.append(entry)
    return {
        "categories": [{"id": c.key, "name": c.name, "imageUrl": c.image_url} for c in cats],
        "products": products_out,
        "modifiers": [{"id": m.key, "group": m.group, "name": m.name, "price": m.price, "effect": m.effect} for m in mods],
        "ingredients": [ingredient_out(i) for i in rows(db, Ingredient, cid)],
    }


@app.get("/api/stock/alerts")
def stock_alerts(ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Low stock of the current branch; min=0 disables alerts for an ingredient."""
    items = []
    levels = branch_stock.levels(ctx.db, ctx.cid, ctx.branch_id)
    refresh_low_stock(ctx.db, ctx.cid, ctx.branch_id)
    ctx.db.commit()
    for ingredient in rows(ctx.db, Ingredient, ctx.cid):
        level = levels[ingredient.key]
        if level["min"] <= 0 or level["stock"] > level["min"]:
            continue
        items.append({
            "id": ingredient.key,
            "name": ingredient.name,
            "unit": ingredient.unit,
            "stock": level["stock"],
            "min": level["min"],
            "shortfall": round(max(0.0, level["min"] - level["stock"]), 6),
        })
    items.sort(key=lambda item: (-item["shortfall"], item["name"], item["id"]))
    return {"count": len(items), "items": items}


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    imageUrl: str | None = Field(default=None, max_length=512)


@app.post("/api/categories")
def add_category(body: CategoryIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    validate_image_url(ctx, body.imageUrl or "")
    sort = len(rows(ctx.db, Category, ctx.cid))
    cat = Category(company_id=ctx.cid, key=slugify(body.name), name=body.name.strip(), sort=sort, image_url=body.imageUrl or "")
    ctx.db.add(cat)
    ctx.db.commit()
    return {"id": cat.key, "name": cat.name, "imageUrl": cat.image_url}


@app.put("/api/categories/{key}")
def rename_category(key: str, body: CategoryIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    cat = get_row(ctx.db, Category, ctx.cid, key)
    if body.imageUrl is not None:
        validate_image_url(ctx, body.imageUrl)
        cat.image_url = body.imageUrl
    cat.name = body.name.strip()
    ctx.db.commit()
    return {"id": cat.key, "name": cat.name, "imageUrl": cat.image_url}


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
    validate_image_url(ctx, body.imageUrl)
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
    if p.combo_components:
        raise HTTPException(409, "Combo mahsulotni Combo bo‘limidan tahrirlang")
    validate_product(ctx, body)
    before = {"name": p.name, "active": p.active, "prices": [{"code": s["code"], "price": s["price"]} for s in p.sizes]}
    p.cat, p.name, p.mods = body.cat, body.name.strip(), body.mods
    p.image_url = body.imageUrl
    p.sizes, p.active = [s.model_dump() for s in body.sizes], body.active
    audit_record(ctx, "product.update", p.id, before,
                 {"name": p.name, "active": p.active, "prices": [{"code": s["code"], "price": s["price"]} for s in p.sizes]})
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
    product = get_row(ctx.db, Product, ctx.cid, key)
    for combo in rows(ctx.db, Product, ctx.cid):
        if any(c["productId"] == key for c in (combo.combo_components or [])):
            raise HTTPException(409, "Mahsulot combo tarkibida ishlatilmoqda")
    ctx.db.delete(product)
    ctx.db.commit()
    return {"ok": True}


class ComboComponentIn(BaseModel):
    productId: str = Field(min_length=1, max_length=64)
    size: str = Field(min_length=1, max_length=16)
    qty: int = Field(ge=1, le=10)


class ComboIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    cat: str
    price: int = Field(ge=0)
    components: list[ComboComponentIn] = Field(min_length=2, max_length=10)
    active: bool = True


def save_combo(body, ctx, product=None):
    get_row(ctx.db, Category, ctx.cid, body.cat)
    components = [c.model_dump() for c in body.components]
    if not body.name.strip() or len({(c["productId"], c["size"]) for c in components}) != len(components):
        raise HTTPException(422, "Combo nomi va tarkibini tekshiring")
    if product is None:
        product = Product(company_id=ctx.cid, key="combo-" + secrets.token_hex(8), sort=len(rows(ctx.db, Product, ctx.cid)))
    product.name, product.cat, product.mods, product.active = body.name.strip(), body.cat, [], body.active
    product.combo_components = components
    product.sizes = [{"code": "-", "label": "Combo", "price": body.price, "recipe": []}]
    resolved = resolve_combo(product, {p.key: p for p in rows(ctx.db, Product, ctx.cid)},
                             {m.key: m for m in rows(ctx.db, Modifier, ctx.cid)},
                             {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)})
    ctx.db.add(product)
    ctx.db.commit()
    return {**product_out(product), "sizes": resolved.sizes}


@app.get("/api/combos")
def list_combos(ctx: Ctx = Depends(require(*MANAGERS))):
    return [product_out(p) for p in rows(ctx.db, Product, ctx.cid) if p.combo_components]


@app.post("/api/combos", status_code=201)
def add_combo(body: ComboIn, ctx: Ctx = Depends(require(*MANAGERS))):
    return save_combo(body, ctx)


@app.put("/api/combos/{key}")
def edit_combo(key: str, body: ComboIn, ctx: Ctx = Depends(require(*MANAGERS))):
    product = get_row(ctx.db, Product, ctx.cid, key)
    if not product.combo_components:
        raise HTTPException(409, "Bu mahsulot combo emas")
    return save_combo(body, ctx, product)


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
    current = branch_stock.get(ctx.db, ctx.cid, ctx.branch_id, i, lock=True)
    if body.reason == "count":
        if body.qty < 0:
            raise HTTPException(400, "Qoldiq manfiy bo'lmaydi")
        delta = body.qty - current
    elif body.qty <= 0:
        raise HTTPException(400, "Miqdor musbat bo'lsin")
    else:
        delta = body.qty if body.reason == "intake" else -body.qty
    note = (body.note or "other") if body.reason == "writeoff" else None
    after = branch_stock.adjust(ctx.db, ctx.cid, ctx.branch_id, i, delta)
    move = StockMove(company_id=ctx.cid, branch_id=ctx.branch_id, ingredient=i.key, qty=delta,
                     reason=body.reason, note=note, staff_name=ctx.staff.name)
    ctx.db.add(move)
    ctx.db.flush()
    audit_record(ctx, f"stock.{body.reason}", move.id, {"ingredient": i.key, "stock": current},
                 {"ingredient": i.key, "stock": after, "delta": delta, "note": note})
    ctx.db.commit()
    return {**ingredient_out(i), "stock": after}


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
    requireApproval: bool = False


def inventory_out(inv: Inventory) -> dict:
    return {
        "id": inv.id, "staff": inv.staff_name, "note": inv.note, "lines": inv.lines,
        "shortage": inv.shortage, "surplus": inv.surplus, "createdAt": inv.created_at,
        "status": inv.status or "approved", "approvedBy": inv.approved_by, "approvedAt": inv.approved_at,
        "branchId": inv.branch_id,
    }


@app.post("/api/inventories")
def create_inventory(body: InventoryIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    keys = [line.ing for line in body.lines]
    if len(set(keys)) != len(keys):
        raise HTTPException(400, "Xomashyo takrorlangan")
    ings = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    inv = Inventory(company_id=ctx.cid, branch_id=ctx.branch_id, staff_id=ctx.staff.id, staff_name=ctx.staff.name,
                    note=body.note.strip(), lines=[], status="pending" if body.requireApproval else "approved",
                    approved_by=None if body.requireApproval else ctx.staff.name,
                    approved_at=None if body.requireApproval else now_ms())
    ctx.db.add(inv)
    ctx.db.flush()
    lines, shortage, surplus = [], 0, 0
    for line in body.lines:
        i = ings.get(line.ing)
        if not i:
            raise HTTPException(404, f"Xomashyo topilmadi: {line.ing}")
        expected = branch_stock.get(ctx.db, ctx.cid, ctx.branch_id, i, lock=True)
        diff = line.counted - expected
        value = round(diff * i.cost)
        if value < 0:
            shortage += -value
        else:
            surplus += value
        lines.append({"ing": i.key, "name": i.name, "unit": i.unit, "expected": expected, "counted": line.counted, "diff": diff, "value": value})
        if diff and not body.requireApproval:
            branch_stock.adjust(ctx.db, ctx.cid, ctx.branch_id, i, diff)
            ctx.db.add(StockMove(company_id=ctx.cid, branch_id=ctx.branch_id, ingredient=i.key, qty=diff,
                                 reason="count", inventory_id=inv.id, staff_name=ctx.staff.name))
    inv.lines, inv.shortage, inv.surplus = lines, shortage, surplus
    audit_record(ctx, "inventory.count", inv.id, {}, {
        "shortage": shortage, "surplus": surplus,
        "lines": [{"ingredient": line["ing"], "expected": line["expected"],
                   "counted": line["counted"], "difference": line["diff"]} for line in lines],
    })
    ctx.db.commit()
    return inventory_out(inv)


@app.get("/api/inventories")
def list_inventories(days: int = 90, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = (
        select(Inventory)
        .where(Inventory.company_id == ctx.cid, Inventory.branch_id == ctx.branch_id,
               Inventory.created_at >= start_of_day_ms(days))
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
    if ctx.staff.role == "kassir" and open_shift(ctx.db, ctx.cid, ctx.branch_id) is None:
        raise HTTPException(409, "Xarajat kiritish uchun smena ochiq bo'lishi kerak")
    e = Expense(company_id=ctx.cid, branch_id=ctx.branch_id, amount=body.amount, category=body.category.strip(),
                description=body.description.strip(), payment=body.payment, staff_name=ctx.staff.name)
    ctx.db.add(e)
    ctx.db.flush()
    audit_record(ctx, "expense.create", e.id, {}, {"amount": e.amount, "category": e.category,
                                                    "payment": e.payment, "branchId": e.branch_id})
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


def masked_phone(phone: str) -> str:
    return "***" + phone[-4:]


@app.get("/api/customers")
def customer_list(before_id: int | None = None, limit: int = 50,
                  ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    if not 1 <= limit <= 100 or (before_id is not None and before_id < 1):
        raise HTTPException(422, "Mijoz filtri noto‘g‘ri")
    query = select(Customer).where(Customer.company_id == ctx.cid, Customer.erased_at.is_(None))
    if before_id is not None:
        query = query.where(Customer.id < before_id)
    customers = ctx.db.scalars(query.order_by(Customer.id.desc()).limit(limit + 1)).all()
    page = customers[:limit]
    return {"items": [{"id": c.id, "name": c.name, "phoneMasked": masked_phone(c.phone),
                       "analyticsConsent": c.analytics_consent, "consentUpdatedAt": c.consent_updated_at}
                      for c in page], "nextCursor": page[-1].id if len(customers) > limit else None}


@app.get("/api/customers/{customer_id}/bonus-ledger")
def customer_bonus_ledger(customer_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    customer = ctx.db.scalar(select(Customer).where(Customer.id == customer_id, Customer.company_id == ctx.cid))
    if customer is None or customer.erased_at is not None:
        raise HTTPException(404, "Mijoz topilmadi")
    entries = ctx.db.scalars(select(BonusLedger).where(
        BonusLedger.company_id == ctx.cid, BonusLedger.customer_id == customer.id
    ).order_by(BonusLedger.id.desc()).limit(500)).all()
    total = ctx.db.scalar(select(func.coalesce(func.sum(BonusLedger.amount), 0)).where(
        BonusLedger.company_id == ctx.cid, BonusLedger.customer_id == customer.id))
    return {"customerId": customer.id, "balance": customer.bonus_balance, "ledgerTotal": int(total),
            "consistent": int(total) == customer.bonus_balance,
            "items": [{"id": e.id, "orderId": e.order_id, "amount": e.amount, "reason": e.reason,
                       "createdAt": e.created_at} for e in entries]}


@app.delete("/api/customers/{customer_id}")
def customer_erase(customer_id: int, ctx: Ctx = Depends(require("owner"))) -> dict:
    """Right to erasure: drop phone/name and bonus balance; sales stay for accounting without PII."""
    customer = ctx.db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.company_id == ctx.cid).with_for_update())
    if customer is None or customer.erased_at is not None:
        raise HTTPException(404, "Mijoz topilmadi")
    if customer.bonus_balance:
        ctx.db.add(BonusLedger(company_id=ctx.cid, customer_id=customer.id, order_id=None,
                               amount=-customer.bonus_balance, reason="erase"))
    customer.bonus_balance = 0
    customer.phone, customer.name = f"erased-{customer.id}", ""
    customer.analytics_consent, customer.consent_updated_at = False, now_ms()
    customer.consent_actor_id, customer.erased_at = ctx.staff.id, now_ms()
    ctx.db.execute(update(Order).where(Order.company_id == ctx.cid, Order.customer_id == customer.id)
                   .values(customer=""))
    audit_record(ctx, "customer.erase", customer.id, {}, {"analyticsConsent": False})
    ctx.db.commit()
    return {"id": customer.id, "erased": True}


class CustomerConsentIn(BaseModel):
    granted: bool
    operatorConfirmed: bool = False


@app.put("/api/customers/{customer_id}/analytics-consent")
def customer_consent(customer_id: int, body: CustomerConsentIn,
                     ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    customer = ctx.db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.company_id == ctx.cid).with_for_update())
    if customer is None:
        raise HTTPException(404, "Mijoz topilmadi")
    if body.granted and not body.operatorConfirmed:
        raise HTTPException(422, "Mijoz roziligi olinganini tasdiqlang")
    if customer.analytics_consent != body.granted:
        before = customer.analytics_consent
        customer.analytics_consent = body.granted
        customer.consent_updated_at, customer.consent_actor_id = now_ms(), ctx.staff.id
        audit_record(ctx, "customer.analytics_consent", customer.id,
                     {"analyticsConsent": before}, {"analyticsConsent": body.granted})
        ctx.db.commit()
    return {"id": customer.id, "analyticsConsent": customer.analytics_consent,
            "consentUpdatedAt": customer.consent_updated_at}


@app.get("/api/reports/customers")
def customer_analytics(days: int = 30, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    if not 1 <= days <= 92:
        raise HTTPException(422, "Davr 1-92 kun bo‘lsin")
    start, end = start_of_day_ms(days - 1), now_ms()
    # Consent is checked at read time, so revocation immediately excludes history.
    consenting_count = ctx.db.scalar(select(func.count(Customer.id)).where(
        Customer.company_id == ctx.cid, Customer.analytics_consent.is_(True)))
    pairs = ctx.db.execute(select(Order, Customer.created_at).join(Customer, (Order.customer_id == Customer.id) &
        (Order.company_id == Customer.company_id)).where(
        Order.company_id == ctx.cid, Customer.analytics_consent.is_(True),
        Order.status != "cancelled", Order.created_at >= start, Order.created_at <= end)).all()
    orders = [pair[0] for pair in pairs]
    visits = {}
    cohorts = {}
    for order, customer_created_at in pairs:
        visits[order.customer_id] = visits.get(order.customer_id, 0) + 1
        cohort = datetime.fromtimestamp(customer_created_at / 1000, TZ).strftime("%Y-%m")
        month = datetime.fromtimestamp(order.created_at / 1000, TZ).strftime("%Y-%m")
        key = (cohort, month)
        entry = cohorts.setdefault(key, {"customers": set(), "orders": 0, "revenue": 0})
        entry["customers"].add(order.customer_id)
        entry["orders"] += 1
        entry["revenue"] += order.total
    return {"days": days, "start": start, "end": end, "consentingCustomers": consenting_count,
            "purchasingCustomers": len(visits), "repeatCustomers": sum(n > 1 for n in visits.values()),
            "orders": len(orders), "revenue": sum(o.total for o in orders),
            "cohorts": [{"cohort": key[0], "month": key[1], "customers": len(v["customers"]),
                         "orders": v["orders"], "revenue": v["revenue"]} for key, v in sorted(cohorts.items())]}


@app.get("/api/customers/{customer_id}/purchases")
def customer_purchases(customer_id: int, before_id: int | None = None,
                       ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    customer = ctx.db.scalar(select(Customer).where(Customer.id == customer_id, Customer.company_id == ctx.cid))
    if customer is None:
        raise HTTPException(404, "Mijoz topilmadi")
    if not customer.analytics_consent:
        raise HTTPException(403, "Mijoz tahlilga rozilik bermagan")
    if before_id is not None and before_id < 1:
        raise HTTPException(422, "Mijoz filtri noto‘g‘ri")
    query = select(Order).where(Order.company_id == ctx.cid, Order.customer_id == customer.id)
    if before_id is not None:
        query = query.where(Order.id < before_id)
    orders = ctx.db.scalars(query.order_by(Order.id.desc()).limit(51)).all()
    return {"items": [{"note": o.note, "guestCount": o.guest_count, "waiter": o.waiter_name, "id": str(o.id), "number": o.number, "createdAt": o.created_at,
                       "total": o.total, "status": o.status} for o in orders[:50]],
            "nextCursor": orders[49].id if len(orders) > 50 else None}


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
    ctx.db.flush()
    audit_record(ctx, "staff.create", s.id, {}, staff_out(s))
    ctx.db.commit()
    return staff_out(s)


@app.put("/api/staff/{sid}")
def update_staff(sid: int, body: StaffIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    s = ctx.db.get(Staff, sid)
    if not s or s.company_id != ctx.cid:
        raise HTTPException(404, "Topilmadi")
    guard_owner(ctx, s.role)
    guard_owner(ctx, body.role)
    before = staff_out(s)
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
    audit_record(ctx, "staff.update", s.id, before, {**staff_out(s), "pinChanged": bool(body.pin)})
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
    # Tenders count in the shift that collected them (a tab may be settled in a later shift).
    for payment in db.scalars(select(OrderPayment).join(Order, Order.id == OrderPayment.order_id).where(
        OrderPayment.company_id == shift.company_id, OrderPayment.shift_id == shift.id,
        Order.status != "cancelled",
    )):
        by_payment[payment.method] = by_payment.get(payment.method, 0) + payment.amount
    # Cash expenses reduce the physically expected register balance.
    cutoff = shift.closed_at if shift.closed_at is not None else now_ms()
    cash_spent = sum(row.amount for row in db.scalars(select(Expense).where(
        Expense.company_id == shift.company_id,
        Expense.branch_id == shift.branch_id,
        Expense.payment == "cash",
        Expense.created_at >= shift.opened_at,
        Expense.created_at <= cutoff,
    )))
    cash_refunded = sum(r.amount for r in db.scalars(select(OrderRefund).where(
        OrderRefund.company_id == shift.company_id,
        OrderRefund.method == "naqd",
        OrderRefund.order_id.in_(select(Order.id).where(Order.company_id == shift.company_id,
                                                        Order.branch_id == shift.branch_id)),
        OrderRefund.created_at >= shift.opened_at,
        OrderRefund.created_at <= cutoff,
    )))
    return {
        "shift": shift_out(shift),
        "cashRefunds": cash_refunded,
        "orders": len(orders),
        "revenue": sum(o.total for o in orders),
        "byPayment": by_payment,
        "cashExpenses": cash_spent,
        "expectedCash": shift.opening_cash + by_payment.get("naqd", 0) - cash_spent - cash_refunded,
    }


@app.post("/api/shifts/open")
def shift_open(body: OpenShiftIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    if open_shift(ctx.db, ctx.cid, ctx.branch_id):
        raise HTTPException(409, "Smena allaqachon ochiq")
    s = Shift(company_id=ctx.cid, branch_id=ctx.branch_id, staff_id=ctx.staff.id, staff_name=ctx.staff.name,
              opening_cash=body.openingCash)
    ctx.db.add(s)
    ctx.db.flush()
    audit_record(ctx, "shift.open", s.id, {}, {"openingCash": s.opening_cash, "branchId": s.branch_id})
    ctx.db.commit()
    return shift_out(s)


@app.get("/api/shifts/current")
def shift_current(ctx: Ctx = Depends(auth)) -> dict | None:
    s = open_shift(ctx.db, ctx.cid, ctx.branch_id)
    return shift_summary(ctx.db, s) if s else None


@app.post("/api/shifts/close")
def shift_close(body: CloseShiftIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    s = open_shift(ctx.db, ctx.cid, ctx.branch_id)
    if not s:
        raise HTTPException(409, "Ochiq smena yo'q")
    summary = shift_summary(ctx.db, s)
    s.closed_at, s.closed_by = now_ms(), ctx.staff.name
    s.closing_cash, s.expected_cash = body.closingCash, summary["expectedCash"]
    audit_record(ctx, "shift.close", s.id, {"expectedCash": summary["expectedCash"]}, {
        "closingCash": body.closingCash, "difference": body.closingCash - summary["expectedCash"],
        "branchId": s.branch_id,
    })
    ctx.db.commit()
    return {**summary, "shift": shift_out(s), "difference": body.closingCash - summary["expectedCash"]}


@app.get("/api/shifts")
def shift_history(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(Shift).where(Shift.company_id == ctx.cid).order_by(Shift.id.desc()).limit(30)
    return [shift_summary(ctx.db, s) for s in ctx.db.scalars(q)]


# ---------- orders ----------

class OrderItemIn(BaseModel):
    guest: int = Field(default=1, ge=1, le=50)
    productId: str
    size: str
    modIds: list[str] = []
    qty: int = 1


class PaymentPartIn(BaseModel):
    method: Literal["naqd", "karta", "payme", "click"]
    amount: int = Field(gt=0)


class OrderIn(BaseModel):
    note: str = Field(default="", max_length=500)
    guestCount: int = Field(default=1, ge=1, le=50)
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    customer: str = Field(default="", max_length=64)
    discountPct: int = Field(default=0, ge=0, le=50)
    payment: Literal["naqd", "karta", "payme", "click", "split"]
    paymentParts: list[PaymentPartIn] | None = Field(default=None, max_length=4)
    cashGiven: int | None = Field(default=None, ge=0)
    expectedTotal: int | None = Field(default=None, ge=0)
    customerPhone: str = Field(default="", max_length=20)
    bonusRedeem: int = Field(default=0, ge=0)
    clientKey: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{12,64}$")
    allowPartial: bool = False
    draftId: int | None = None
    draftVersion: int | None = Field(default=None, ge=1)
    offline: bool = False
    offlineCreatedAt: int | None = Field(default=None, ge=0)


# ---------- parked orders (no payment, no stock deduction) ----------
def draft_table_name(db: Session, draft: DraftOrder | None) -> str | None:
    if draft is None or draft.table_id is None:
        return None
    table = db.get(DiningTable, draft.table_id)
    return table.name if table is not None else None


class DraftOrderIn(BaseModel):
    note: str = Field(default="", max_length=500)
    guestCount: int = Field(default=1, ge=1, le=50)
    clientKey: str = Field(pattern=r"^[a-zA-Z0-9_-]{12,64}$")
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    customer: str = Field(default="", max_length=64)
    tableId: int | None = None
    service: Literal["takeaway", "dine_in"] = "takeaway"


class DraftOrderUpdate(BaseModel):
    note: str = Field(default="", max_length=500)
    guestCount: int = Field(default=1, ge=1, le=50)
    version: int = Field(ge=1)
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    customer: str = Field(default="", max_length=64)


def draft_out(draft: DraftOrder) -> dict:
    return {"id": draft.id, "clientKey": draft.client_key, "items": draft.items,
            "customer": draft.customer, "staff": draft.staff_name, "note": draft.note, "guestCount": draft.guest_count, "waiter": draft.waiter_name,
            "version": draft.version, "createdAt": draft.created_at,
            "updatedAt": draft.updated_at, "tableId": draft.table_id, "service": draft.service or "takeaway"}


@app.get("/api/drafts")
def list_drafts(ctx: Ctx = Depends(require(*CASHIERS))) -> list[dict]:
    drafts = ctx.db.scalars(select(DraftOrder).where(
        DraftOrder.company_id == ctx.cid, DraftOrder.branch_id == ctx.branch_id
    ).order_by(DraftOrder.updated_at.desc()).limit(100)).all()
    return [draft_out(d) for d in drafts]


@app.post("/api/drafts", status_code=201)
def create_draft(body: DraftOrderIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    existing = ctx.db.scalar(select(DraftOrder).where(
        DraftOrder.company_id == ctx.cid, DraftOrder.client_key == body.clientKey
    ))
    if existing:
        if existing.branch_id != ctx.branch_id:
            raise HTTPException(409, "Qoralama kaliti boshqa buyurtmaga tegishli")
        if existing.items != [item.model_dump() for item in body.items] or existing.customer != body.customer or existing.note != body.note or existing.guest_count != max(body.guestCount, max(i.guest for i in body.items)):
            raise HTTPException(409, "Qoralama kaliti boshqa buyurtmaga tegishli")
        return draft_out(existing)
    table = validate_table(ctx, body.tableId, body.service)
    if table is not None and ctx.db.scalar(select(DraftOrder.id).where(
            DraftOrder.company_id == ctx.cid, DraftOrder.table_id == table.id)) is not None:
        raise HTTPException(409, "Stol band")
    draft = DraftOrder(company_id=ctx.cid, branch_id=ctx.branch_id, client_key=body.clientKey,
                       items=[item.model_dump() for item in body.items],
                       customer=body.customer, note=body.note, guest_count=max(body.guestCount, max(i.guest for i in body.items)), staff_name=ctx.staff.name,
                       table_id=table.id if table else None, service=body.service)
    ctx.db.add(draft)
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise HTTPException(409, "Qoralama kaliti allaqachon mavjud")
    ctx.db.refresh(draft)
    return draft_out(draft)


@app.patch("/api/drafts/{draft_id}")
def update_draft(draft_id: int, body: DraftOrderUpdate,
                 ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    result = ctx.db.execute(update(DraftOrder).where(
        DraftOrder.id == draft_id, DraftOrder.company_id == ctx.cid, DraftOrder.branch_id == ctx.branch_id,
        DraftOrder.version == body.version
    ).values(items=[item.model_dump() for item in body.items],
             customer=body.customer, note=body.note, guest_count=max(body.guestCount, max(i.guest for i in body.items)), version=body.version + 1,
             updated_at=now_ms()))
    if result.rowcount != 1:
        ctx.db.rollback()
        exists = ctx.db.scalar(select(DraftOrder.id).where(
            DraftOrder.id == draft_id, DraftOrder.company_id == ctx.cid, DraftOrder.branch_id == ctx.branch_id
        ))
        raise HTTPException(409 if exists else 404,
                            "Qoralama boshqa qurilmada o‘zgargan. Yangilab qayta tekshiring" if exists else "Qoralama topilmadi")
    ctx.db.commit()
    draft = ctx.db.scalar(select(DraftOrder).where(
        DraftOrder.id == draft_id, DraftOrder.company_id == ctx.cid, DraftOrder.branch_id == ctx.branch_id
    ))
    return draft_out(draft)


@app.delete("/api/drafts/{draft_id}", status_code=204)
def delete_draft(draft_id: int, version: int,
                 ctx: Ctx = Depends(require(*CASHIERS))) -> None:
    result = ctx.db.execute(
        delete(DraftOrder).where(
            DraftOrder.id == draft_id, DraftOrder.company_id == ctx.cid, DraftOrder.branch_id == ctx.branch_id,
            DraftOrder.version == version
        )
    )
    if result.rowcount != 1:
        ctx.db.rollback()
        exists = ctx.db.scalar(select(DraftOrder.id).where(
            DraftOrder.id == draft_id, DraftOrder.company_id == ctx.cid, DraftOrder.branch_id == ctx.branch_id
        ))
        raise HTTPException(409 if exists else 404,
                            "Qoralama boshqa qurilmada o‘zgargan. Yangilab qayta tekshiring" if exists else "Qoralama topilmadi")
    ctx.db.commit()


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
    """Offline replays are cash-only; rejected replays become reviewable conflicts, never silent drops."""
    if not body.offline:
        return checkout(body, ctx)
    if body.payment != "naqd" or body.bonusRedeem or body.allowPartial or not body.clientKey or body.draftId:
        raise HTTPException(422, "Oflayn savdo faqat naqd, bonussiz va clientKey bilan bo‘ladi")
    try:
        return checkout(body, ctx)
    except HTTPException as exc:
        if exc.status_code not in (400, 404, 409, 422):
            raise
        ctx.db.rollback()
        conflict = ctx.db.scalar(select(OfflineConflict).where(
            OfflineConflict.company_id == ctx.cid, OfflineConflict.client_key == body.clientKey))
        if conflict is None:
            conflict = OfflineConflict(company_id=ctx.cid, branch_id=ctx.branch_id, client_key=body.clientKey,
                                       body=body.model_dump(), reason=str(exc.detail)[:200],
                                       staff_name=ctx.staff.name)
            ctx.db.add(conflict)
            try:
                ctx.db.commit()
            except IntegrityError:
                ctx.db.rollback()
                conflict = ctx.db.scalar(select(OfflineConflict).where(
                    OfflineConflict.company_id == ctx.cid, OfflineConflict.client_key == body.clientKey))
        raise HTTPException(409, {"code": "offline_conflict", "conflictId": conflict.id,
                                  "reason": conflict.reason}) from exc


def conflict_out(c: OfflineConflict) -> dict:
    return {"id": c.id, "clientKey": c.client_key, "branchId": c.branch_id, "reason": c.reason,
            "status": c.status, "staff": c.staff_name, "resolvedBy": c.resolved_by, "createdAt": c.created_at,
            "items": c.body.get("items", []), "expectedTotal": c.body.get("expectedTotal"),
            "offlineCreatedAt": c.body.get("offlineCreatedAt")}


@app.get("/api/offline/conflicts")
def offline_conflicts(status: Literal["open", "resolved"] = "open",
                      ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    q = select(OfflineConflict).where(OfflineConflict.company_id == ctx.cid, OfflineConflict.status == status)
    if ctx.staff.branch_id is not None:
        q = q.where(OfflineConflict.branch_id == ctx.staff.branch_id)
    return [conflict_out(c) for c in ctx.db.scalars(q.order_by(OfflineConflict.id.desc()).limit(200))]


@app.post("/api/offline/conflicts/{conflict_id}/resolve")
def resolve_offline_conflict(conflict_id: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    conflict = ctx.db.scalar(select(OfflineConflict).where(
        OfflineConflict.id == conflict_id, OfflineConflict.company_id == ctx.cid).with_for_update())
    if conflict is None or (ctx.staff.branch_id is not None and conflict.branch_id != ctx.staff.branch_id):
        raise HTTPException(404, "Ziddiyat topilmadi")
    if conflict.status != "open":
        raise HTTPException(409, "Ziddiyat allaqachon yopilgan")
    conflict.status, conflict.resolved_by = "resolved", ctx.staff.name
    audit_record(ctx, "offline.resolve", conflict.id, {"status": "open"}, {"status": "resolved"})
    ctx.db.commit()
    return conflict_out(conflict)


def checkout(body: OrderIn, ctx: Ctx) -> dict:
    db, cid = ctx.db, ctx.cid
    if body.clientKey:
        existing = db.scalar(select(Order).where(
            Order.company_id == cid, Order.client_key == body.clientKey
        ))
        if existing:
            return order_out(existing)
    shift = open_shift(db, cid, ctx.branch_id)
    if not shift:
        raise HTTPException(409, "Avval smenani oching")
    draft = None
    if body.draftId is not None:
        draft = db.scalar(select(DraftOrder).where(
            DraftOrder.id == body.draftId, DraftOrder.company_id == cid,
            DraftOrder.branch_id == ctx.branch_id).with_for_update())
        if draft is None:
            raise HTTPException(404, "Qoralama topilmadi yoki allaqachon yopilgan")
        if body.draftVersion is None or draft.version != body.draftVersion:
            raise HTTPException(409, "Qoralama boshqa qurilmada o‘zgargan. Yangilab qayta tekshiring")
    prods = {p.key: p for p in rows(db, Product, cid)}
    mods = {m.key: m for m in rows(db, Modifier, cid)}
    ings = {i.key: i for i in rows(db, Ingredient, cid)}

    items: list[dict] = []
    for it in body.items:
        product = prods.get(it.productId)
        if not product:
            raise HTTPException(400, "Mahsulot topilmadi")
        resolved = resolve_combo(product, prods, mods, ings)
        built = build_item(resolved, it.size, it.modIds, it.qty, mods, ings)
        if it.guest > 1:
            built["guest"] = it.guest
            built["key"] += f"|guest:{it.guest}"
        if getattr(resolved, "combo_items", None):
            built["components"] = resolved.combo_items
        same = next((x for x in items if x["key"] == built["key"]), None)
        if same:
            same["qty"] += built["qty"]
        else:
            items.append(built)

    subtotal = sum(i["unitPrice"] * i["qty"] for i in items)
    promotion = choose_promotion(rows(db, Promotion, cid), datetime.now(TZ), shift.branch_id)
    if promotion and body.expectedTotal is None:
        raise HTTPException(409, "Aksiya faol. Kassani yangilang va summani tekshiring")
    manual_discount = discount_amount(subtotal, body.discountPct)
    promo_discount = capped_discount(subtotal, promotion.percent, promotion.max_discount or 0) if promotion else 0
    if promotion and promo_discount < manual_discount:
        promotion = None
    discount = max(manual_discount, promo_discount)
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
    if body.expectedTotal is not None and body.expectedTotal != total:
        raise HTTPException(409, "Narx yoki aksiya o‘zgardi. Summani yangilab qayta tekshiring")
    payment_status = "paid"
    if body.payment == "split":
        minimum_parts = 1 if body.allowPartial else 2
        if body.paymentParts is None or len(body.paymentParts) < minimum_parts:
            raise HTTPException(422, "Bo‘lingan to‘lov uchun kamida 2 usul kerak")
        methods = [p.method for p in body.paymentParts]
        if len(set(methods)) != len(methods):
            raise HTTPException(422, "To‘lov usullari takrorlanmasin")
        parts = [PaymentPart(method=p.method, amount=p.amount) for p in body.paymentParts]
        collected = sum(p.amount for p in parts)
        if body.allowPartial and collected < total:
            payment_status = "partial"
        else:
            try:
                validate_split_payment(total, parts)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
    else:
        if body.paymentParts is not None:
            raise HTTPException(422, "Oddiy to‘lovda paymentParts bo‘lmasin")
        if body.allowPartial:
            raise HTTPException(422, "Qisman to‘lov faqat bo‘lingan to‘lovda")
        parts = [PaymentPart(method=body.payment, amount=total)]
    cash_amount = next((p.amount for p in parts if p.method == "naqd"), 0)
    if body.cashGiven is not None and (cash_amount == 0 or body.cashGiven < cash_amount):
        raise HTTPException(400, "Berilgan pul yetarli emas")

    day_orders = db.scalars(
        select(Order.number).where(Order.company_id == cid, Order.branch_id == shift.branch_id,
                                   Order.created_at >= start_of_day_ms())
    ).all()
    order = Order(
        company_id=cid, shift_id=shift.id, branch_id=shift.branch_id, staff_id=ctx.staff.id,
        number=max(day_orders, default=0) + 1, customer=body.customer.strip(),
        note=body.note, guest_count=max(body.guestCount, max(i.guest for i in body.items)), waiter_name=draft.waiter_name if draft else "",
        customer_id=customer.id if customer is not None else None, bonus_used=redeemed, bonus_earned=earned,
        client_key=body.clientKey,
        promotion_snapshot={"id": promotion.id, "name": promotion.name, "percent": promotion.percent,
                            "maxDiscount": promotion.max_discount or 0, "amount": promo_discount,
                            "timezone": str(TZ)} if promotion else None,
        service=draft.service if draft is not None else "takeaway",
        table_name=draft_table_name(db, draft),
        items=items, subtotal=subtotal, discount=discount, total=total,
        cost=sum(i["unitCost"] * i["qty"] for i in items), payment=body.payment,
        payment_parts=[{"method": p.method, "amount": p.amount} for p in parts],
        cash_given=body.cashGiven if cash_amount else None, staff_name=ctx.staff.name,
        payment_status=payment_status,
    )
    db.add(order)
    db.flush()
    payment_key = body.clientKey or f"order-{order.id}"
    for index, part in enumerate(parts):
        db.add(OrderPayment(company_id=cid, branch_id=shift.branch_id, order_id=order.id, shift_id=shift.id,
                            method=part.method, amount=part.amount, client_key=f"{payment_key}-p{index}",
                            staff_id=ctx.staff.id, staff_name=ctx.staff.name))
    order.fiscal_status = fiscalize(db, cid, order.id, total, "sale", f"sale-{order.id}")
    if draft is not None:
        audit_record(ctx, "draft.checkout", draft.id, {"version": draft.version}, {"orderId": order.id})
        db.delete(draft)
    if customer is not None:
        if redeemed:
            db.add(BonusLedger(company_id=cid, customer_id=customer.id, order_id=order.id,
                               amount=-redeemed, reason="redeem"))
        if earned:
            db.add(BonusLedger(company_id=cid, customer_id=customer.id, order_id=order.id,
                               amount=earned, reason="earn"))
    used: dict[str, float] = {}
    for it in items:
        for line in it["consumption"]:
            used[line["ing"]] = used.get(line["ing"], 0) + line["qty"] * it["qty"]
    for key, qty in used.items():
        if key in ings:
            branch_stock.adjust(db, cid, shift.branch_id, ings[key], -qty)
            db.add(StockMove(company_id=cid, branch_id=shift.branch_id, ingredient=key, qty=-qty, reason="sale",
                             order_id=order.id, staff_name=ctx.staff.name))
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
    return order_out(order)


@app.post("/api/orders/{oid}/receipt-link")
def receipt_link(oid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    order = ctx.db.scalar(select(Order).where(Order.id == oid, Order.company_id == ctx.cid).with_for_update())
    if order is None:
        raise HTTPException(404, "Buyurtma topilmadi")
    token, grant = make_receipt_token(ctx.db, order)
    audit_record(ctx, "receipt.issue", order.id, {}, {"status": "active"})
    ctx.db.commit()
    return {"path": "/api/public/receipts/" + token, "linkId": grant.id,
            "expiresIn": RECEIPT_TTL, "fiscal": False}


@app.delete("/api/orders/{oid}/receipt-links")
def revoke_receipt_links(oid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    # Serialize issue/revoke through the order row on PostgreSQL.
    order = ctx.db.scalar(select(Order).where(Order.id == oid, Order.company_id == ctx.cid).with_for_update())
    if order is None:
        raise HTTPException(404, "Buyurtma topilmadi")
    result = ctx.db.execute(update(ReceiptLink).where(
        ReceiptLink.order_id == oid, ReceiptLink.company_id == ctx.cid,
        ReceiptLink.revoked_at.is_(None), ReceiptLink.expires_at > now_ms()
    ).values(revoked_at=now_ms()))
    count = result.rowcount
    if count:
        audit_record(ctx, "receipt.revoke", oid, {"status": "active"}, {"status": "revoked"})
    ctx.db.commit()
    return {"revoked": count}


@app.get("/api/public/receipts/{token}", response_class=HTMLResponse)
def public_receipt(token: str, lang: Literal["uz", "ru"] = "uz", db: Session = Depends(get_db)):
    claims = read_receipt_token(db, token)
    if not claims:
        raise HTTPException(404, "Chek havolasi yaroqsiz yoki muddati tugagan")
    order = db.scalar(select(Order).where(Order.id == claims["oid"], Order.company_id == claims["cid"]))
    company = db.get(Company, claims["cid"])
    if order is None or company is None:
        raise HTTPException(404, "Chek havolasi yaroqsiz yoki muddati tugagan")
    refunded = sum(db.scalars(select(OrderRefund.amount).where(
        OrderRefund.company_id == company.id, OrderRefund.order_id == order.id)))
    fiscal = sale_receipt(db, company.id, order.id)
    return HTMLResponse(receipt_html(order, company.name, refunded, lang, TZ, fiscal), headers={
        "Cache-Control": "no-store, private", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex, nofollow, noarchive",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    })


# ---------- manually recorded refunds (no payment gateway action) ----------

class RefundItemIn(BaseModel):
    key: str = Field(min_length=1, max_length=256)
    qty: int = Field(gt=0, le=999)


class RefundIn(BaseModel):
    clientKey: str = Field(pattern=r"^[a-zA-Z0-9_-]{12,64}$")
    amount: int = Field(gt=0)
    method: Literal["naqd", "karta", "payme", "click"]
    reason: str = Field(min_length=3, max_length=256)
    externalConfirmed: bool
    items: list[RefundItemIn] | None = Field(default=None, max_length=50)
    restock: bool = False


class PaymentIn(BaseModel):
    clientKey: str = Field(pattern=r"^[a-zA-Z0-9_-]{12,64}$")
    method: Literal["naqd", "karta", "payme", "click"]
    amount: int = Field(gt=0)


@app.post("/api/orders/{oid}/payments", status_code=201)
def add_order_payment(oid: int, body: PaymentIn, ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    """Settle the outstanding part of a partially paid order (idempotent per clientKey)."""
    db = ctx.db
    order = db.scalar(select(Order).where(Order.id == oid, Order.company_id == ctx.cid).with_for_update())
    if order is None:
        raise HTTPException(404, "Buyurtma topilmadi")
    existing = db.scalar(select(OrderPayment).where(OrderPayment.company_id == ctx.cid,
                                                    OrderPayment.client_key == body.clientKey))
    if existing is not None:
        if (existing.order_id, existing.method, existing.amount) != (oid, body.method, body.amount):
            raise HTTPException(409, "To‘lov kaliti boshqa operatsiyaga tegishli")
        return order_out(order)
    if order.status == "cancelled":
        raise HTTPException(409, "Bekor qilingan buyurtma")
    if order.payment_status != "partial":
        raise HTTPException(409, "Buyurtma to‘liq to‘langan")
    if ctx.staff.branch_id is not None and order.branch_id != ctx.staff.branch_id:
        raise HTTPException(403, "Bu filial uchun ruxsat yo'q")
    shift = open_shift(db, ctx.cid, order.branch_id)
    if shift is None:
        raise HTTPException(409, "Avval smenani oching")
    parts = list(order_payment_parts(order))
    outstanding = order.total - sum(p["amount"] for p in parts)
    if body.amount > outstanding:
        raise HTTPException(422, "To‘lov qoldiqdan oshmasin")
    db.add(OrderPayment(company_id=ctx.cid, branch_id=order.branch_id, order_id=order.id, shift_id=shift.id,
                        method=body.method, amount=body.amount, client_key=body.clientKey,
                        staff_id=ctx.staff.id, staff_name=ctx.staff.name))
    merged = {p["method"]: p["amount"] for p in parts}
    merged[body.method] = merged.get(body.method, 0) + body.amount
    order.payment_parts = [{"method": k, "amount": v} for k, v in merged.items()]
    if body.amount == outstanding:
        order.payment_status = "paid"
    audit_record(ctx, "order.payment", order.id, {"outstanding": outstanding},
                 {"method": body.method, "amount": body.amount, "outstanding": outstanding - body.amount})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "To‘lov allaqachon saqlangan; qayta tekshiring") from None
    return order_out(order)


def refund_out(refund: OrderRefund) -> dict:
    return {
        "id": refund.id, "orderId": refund.order_id, "clientKey": refund.client_key,
        "amount": refund.amount, "method": refund.method, "reason": refund.reason,
        "staff": refund.staff_name, "createdAt": refund.created_at,
        "items": refund.items or [], "restocked": bool(refund.restocked), "costReversed": refund.cost_reversed or 0,
        "bonusReversed": refund.bonus_reversed or 0, "bonusRestored": refund.bonus_restored or 0,
        "fiscalStatus": refund.fiscal_status or "nonfiscal",
    }


@app.get("/api/orders/{oid}/refunds")
def list_order_refunds(oid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    order = ctx.db.scalar(select(Order.id).where(Order.id == oid, Order.company_id == ctx.cid))
    if order is None:
        raise HTTPException(404, "Buyurtma topilmadi")
    refunds = ctx.db.scalars(select(OrderRefund).where(
        OrderRefund.company_id == ctx.cid, OrderRefund.order_id == oid
    ).order_by(OrderRefund.id)).all()
    return [refund_out(r) for r in refunds]


@app.post("/api/orders/{oid}/refunds", status_code=201)
def record_refund(oid: int, body: RefundIn, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Audit an already completed refund. No transfer is initiated by this endpoint.

    Do not restore ingredients here: financial refunds and physical returns are
    distinct events. Gateway reversals must be verified outside this API.
    """
    if not body.externalConfirmed:
        raise HTTPException(422, "Pul qaytarilgani tashqarida tasdiqlanishi kerak")
    reason = body.reason.strip()
    if len(reason) < 3:
        raise HTTPException(422, "Qaytarish sababini kiriting")

    requested_items = sorted((i.key, i.qty) for i in body.items or [])

    def replay(existing: OrderRefund) -> dict:
        stored_items = sorted((i["key"], i["qty"]) for i in existing.items or [])
        if (existing.order_id, existing.amount, existing.method, existing.reason, stored_items,
                bool(existing.restocked)) != (oid, body.amount, body.method, reason, requested_items, body.restock):
            raise HTTPException(409, "Qaytarish kaliti boshqa operatsiyaga tegishli")
        return refund_out(existing)

    existing = ctx.db.scalar(select(OrderRefund).where(
        OrderRefund.company_id == ctx.cid, OrderRefund.client_key == body.clientKey
    ))
    if existing:
        return replay(existing)
    order = ctx.db.scalar(select(Order).where(
        Order.id == oid, Order.company_id == ctx.cid
    ).with_for_update())
    if order is None:
        raise HTTPException(404, "Buyurtma topilmadi")
    # Another request with the same key may have committed while we waited for
    # the order lock. Recheck before calculating the remaining refundable sum.
    existing = ctx.db.scalar(select(OrderRefund).where(
        OrderRefund.company_id == ctx.cid, OrderRefund.client_key == body.clientKey
    ))
    if existing:
        return replay(existing)
    if order.status == "cancelled":
        raise HTTPException(409, "Bekor qilingan buyurtma uchun refund mumkin emas")
    paid = {part["method"]: part["amount"] for part in order_payment_parts(order)}
    if body.method not in paid:
        raise HTTPException(422, "Ushbu usul bilan to‘lov olinmagan")
    refunds = ctx.db.scalars(select(OrderRefund).where(
        OrderRefund.company_id == ctx.cid, OrderRefund.order_id == oid
    )).all()
    already = sum(refund.amount for refund in refunds if refund.method == body.method)
    try:
        validate_refund(paid=paid[body.method], already_refunded=already, requested=body.amount)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if body.restock and not body.items:
        raise HTTPException(422, "Omborga qaytarish uchun qaytarilgan mahsulotlarni tanlang")
    returned_lines: list[dict] = []
    cost_reversed = 0
    if body.items:
        sold = {item["key"]: item for item in order.items}
        returned_before: dict[str, int] = {}
        for previous in refunds:
            for line in previous.items or []:
                returned_before[line["key"]] = returned_before.get(line["key"], 0) + line["qty"]
        gross = 0
        for line in body.items:
            item = sold.get(line.key)
            if item is None:
                raise HTTPException(422, "Buyurtmada bunday mahsulot yo‘q")
            if line.qty + returned_before.get(line.key, 0) > item["qty"]:
                raise HTTPException(422, "Qaytarilgan miqdor sotilganidan oshmasin")
            returned_before[line.key] = returned_before.get(line.key, 0) + line.qty
            gross += item["unitPrice"] * line.qty
            returned_lines.append({"key": line.key, "name": item["name"], "qty": line.qty,
                                   "unitPrice": item["unitPrice"], "unitCost": item["unitCost"]})
        # Proportional share of order-level discounts and redeemed bonus.
        if order.subtotal and body.amount > gross * order.total // order.subtotal:
            raise HTTPException(422, "Qaytarish summasi tanlangan mahsulotlar qiymatidan oshmasin")
        if body.restock:
            ingredients = {i.key: i for i in ctx.db.scalars(select(Ingredient).where(
                Ingredient.company_id == ctx.cid).with_for_update())}
            restore: dict[str, float] = {}
            for line in returned_lines:
                cost_reversed += line["unitCost"] * line["qty"]
                for use in sold[line["key"]]["consumption"]:
                    restore[use["ing"]] = restore.get(use["ing"], 0) + use["qty"] * line["qty"]
            for key, qty in restore.items():
                if key in ingredients:
                    branch_stock.adjust(ctx.db, ctx.cid, order.branch_id, ingredients[key], qty)
                    ctx.db.add(StockMove(company_id=ctx.cid, branch_id=order.branch_id, ingredient=key, qty=qty,
                                         reason="refund_return", order_id=order.id, staff_name=ctx.staff.name))
    bonus_reversed = bonus_restored = 0
    if order.customer_id is not None and (order.bonus_earned or order.bonus_used) and order.total:
        customer = ctx.db.scalar(select(Customer).where(
            Customer.id == order.customer_id, Customer.company_id == ctx.cid).with_for_update())
        if customer is not None and customer.erased_at is None:
            # Return the redeemed share first, then claw back earned points; never below zero.
            bonus_restored = order.bonus_used * body.amount // order.total
            if bonus_restored:
                customer.bonus_balance += bonus_restored
                ctx.db.add(BonusLedger(company_id=ctx.cid, customer_id=customer.id, order_id=order.id,
                                       amount=bonus_restored, reason="refund_restore"))
            due = order.bonus_earned * body.amount // order.total
            bonus_reversed = min(due, max(0, customer.bonus_balance))
            if bonus_reversed:
                customer.bonus_balance -= bonus_reversed
                ctx.db.add(BonusLedger(company_id=ctx.cid, customer_id=customer.id, order_id=order.id,
                                       amount=-bonus_reversed, reason="refund_reverse"))
    refund = OrderRefund(company_id=ctx.cid, order_id=oid, staff_id=ctx.staff.id, client_key=body.clientKey,
                         amount=body.amount, method=body.method,
                         reason=reason, staff_name=ctx.staff.name, items=returned_lines or None,
                         restocked=body.restock, cost_reversed=cost_reversed, bonus_reversed=bonus_reversed,
                         bonus_restored=bonus_restored,
                         fiscal_status="nonfiscal")
    ctx.db.add(refund)
    try:
        ctx.db.flush()
        refund.fiscal_status = fiscalize(ctx.db, ctx.cid, order.id, refund.amount, "refund",
                                         f"refund-{refund.id}", refund.id)
        audit_record(ctx, "order.refund", refund.id, {}, {
            "orderId": oid, "amount": refund.amount, "method": refund.method,
            "items": [{"key": line["key"], "qty": line["qty"]} for line in returned_lines],
            "restocked": body.restock, "costReversed": cost_reversed, "bonusReversed": bonus_reversed,
        })
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise HTTPException(409, "Qaytarish allaqachon saqlangan; qayta tekshiring")
    ctx.db.refresh(refund)
    return refund_out(refund)


class CancelOrderIn(BaseModel):
    reason: str = Field(min_length=3, max_length=256)


@app.post("/api/orders/{oid}/cancel")
def cancel_order(oid: int, body: CancelOrderIn, ctx: Ctx = Depends(auth)) -> dict:
    if ctx.staff.role not in MANAGERS and not (ctx.staff.role == "kassir" and ctx.staff.can_cancel_orders):
        raise HTTPException(403, "Otmena uchun dostup berilmagan")
    # Serialize cancellation with refunds and other cancellations for this order.
    order = ctx.db.scalar(select(Order).where(
        Order.id == oid, Order.company_id == ctx.cid
    ).with_for_update())
    if order is None:
        raise HTTPException(404, "Buyurtma topilmadi")
    if order.status != "new":
        raise HTTPException(409, "Faqat hali tayyorlanmagan buyurtmani bekor qilish mumkin")
    if ctx.db.scalar(select(OrderRefund.id).where(
        OrderRefund.company_id == ctx.cid, OrderRefund.order_id == order.id
    )):
        raise HTTPException(409, "Qisman yoki to‘liq refund qayd etilgan buyurtmani bekor qilib bo‘lmaydi")
    shift = open_shift(ctx.db, ctx.cid, ctx.branch_id)
    if shift is None or order.shift_id != shift.id:
        raise HTTPException(409, "Yopilgan smenadagi buyurtmani bekor qilib bo'lmaydi")
    ingredients = {i.key: i for i in rows(ctx.db, Ingredient, ctx.cid)}
    moves = ctx.db.scalars(select(StockMove).where(
        StockMove.company_id == ctx.cid, StockMove.order_id == order.id, StockMove.reason == "sale"
    )).all()
    for move in moves:
        item = ingredients.get(move.ingredient)
        if item is not None:
            branch_stock.adjust(ctx.db, ctx.cid, order.branch_id, item, -move.qty)
            ctx.db.add(StockMove(company_id=ctx.cid, branch_id=order.branch_id, ingredient=move.ingredient,
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
    audit_record(ctx, "order.cancel", order.id, {"status": "new"}, {"status": "cancelled", "amount": order.total})
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
    q = select(Order).where(Order.company_id == cid, Order.branch_id == ctx.branch_id,
                            Order.created_at >= since).order_by(Order.id)
    shift = open_shift(db, cid, ctx.branch_id)
    return {
        "branchId": ctx.branch_id,
        "orders": [order_out(o) for o in db.scalars(q)],
        "stock": {key: level["stock"] for key, level in branch_stock.levels(db, cid, ctx.branch_id).items()},
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
        day = [o for o in orders if lo <= o.created_at < hi and o.status != "cancelled"]
        out.append({"day": lo, "revenue": sum(o.total for o in day), "cost": sum(o.cost for o in day), "orders": len(day)})
    return out

# ---------- management financial snapshot ----------
@app.get("/api/audit")
def audit_history(before_id: int | None = None, limit: int = 50, action: str = "",
                  ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    if limit < 1 or limit > 100 or (before_id is not None and before_id < 1):
        raise HTTPException(422, "Audit filtri noto‘g‘ri")
    query = select(AuditEvent).where(AuditEvent.company_id == ctx.cid)
    if before_id is not None:
        query = query.where(AuditEvent.id < before_id)
    if action:
        query = query.where(AuditEvent.action == action)
    events = ctx.db.scalars(query.order_by(AuditEvent.id.desc()).limit(limit + 1)).all()
    page = events[:limit]
    return {"items": [{"id": e.id, "actorId": e.actor_id, "actor": e.actor_name,
                       "action": e.action, "entityId": e.entity_id, "before": e.before,
                       "after": e.after, "createdAt": e.created_at} for e in page],
            "nextCursor": page[-1].id if len(events) > limit else None}


class PromotionIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    startTime: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    endTime: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    weekdays: list[int] = Field(min_length=1, max_length=7)
    percent: int = Field(ge=1, le=50)
    priority: int = Field(default=0, ge=0, le=100)
    active: bool = True
    maxDiscount: int = Field(default=0, ge=0, le=100_000_000)
    branchId: int | None = None


def promotion_out(p):
    return {"id": p.id, "name": p.name, "startTime": p.start_time, "endTime": p.end_time,
            "weekdays": p.weekdays, "percent": p.percent, "priority": p.priority, "active": p.active,
            "maxDiscount": p.max_discount or 0, "branchId": p.branch_id}


@app.get("/api/promotions/active")
def active_promotion(ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    now = datetime.now(TZ)
    promotion = choose_promotion(rows(ctx.db, Promotion, ctx.cid), now, ctx.branch_id)
    return {"timezone": str(TZ), "serverTime": now.isoformat(),
            "promotion": promotion_out(promotion) if promotion else None}


@app.get("/api/promotions")
def list_promotions(ctx: Ctx = Depends(require(*MANAGERS))) -> list[dict]:
    return [promotion_out(p) for p in rows(ctx.db, Promotion, ctx.cid)]


def save_promotion(body, ctx, promotion=None):
    if not body.name.strip() or body.startTime == body.endTime or any(type(d) is not int or d < 0 or d > 6 for d in body.weekdays) or len(set(body.weekdays)) != len(body.weekdays):
        raise HTTPException(422, "Aksiya jadvalini tekshiring")
    if body.branchId is not None:
        branch = ctx.db.get(Branch, body.branchId)
        if branch is None or branch.company_id != ctx.cid:
            raise HTTPException(404, "Filial topilmadi")
    if promotion is None:
        promotion = Promotion(company_id=ctx.cid)
        ctx.db.add(promotion)
    promotion.max_discount, promotion.branch_id = body.maxDiscount, body.branchId
    promotion.name, promotion.start_time, promotion.end_time = body.name.strip(), body.startTime, body.endTime
    promotion.weekdays, promotion.percent = body.weekdays, body.percent
    promotion.priority, promotion.active = body.priority, body.active
    ctx.db.commit()
    return promotion_out(promotion)


@app.post("/api/promotions", status_code=201)
def add_promotion(body: PromotionIn, ctx: Ctx = Depends(require(*MANAGERS))):
    return save_promotion(body, ctx)


@app.put("/api/promotions/{pid}")
def edit_promotion(pid: int, body: PromotionIn, ctx: Ctx = Depends(require(*MANAGERS))):
    promotion = ctx.db.scalar(select(Promotion).where(Promotion.id == pid, Promotion.company_id == ctx.cid))
    if promotion is None:
        raise HTTPException(404, "Topilmadi")
    return save_promotion(body, ctx, promotion)


@app.get("/api/reports/staff")
def staff_report(from_ms: int, to_ms: int, branchId: int | None = None,
                 ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Historical name snapshots; refunds attributed to the original seller by refund date."""
    if to_ms <= from_ms or to_ms - from_ms > 366 * 86400000:
        raise HTTPException(400, "Sana oralig'i 1-366 kun bo'lishi kerak")
    db, cid = ctx.db, ctx.cid
    branch_id = report_branch(ctx, branchId)
    order_q = select(Order).where(Order.company_id == cid, Order.created_at >= from_ms, Order.created_at < to_ms)
    if branch_id is not None:
        order_q = order_q.where(Order.branch_id == branch_id)
    orders = db.scalars(order_q).all()
    result = {}
    shifts = {}

    def row(name):
        if name not in result:
            result[name] = {"name": name, "count": 0, "revenue": 0, "discounts": 0,
                            "refunds": 0, "netRevenue": 0, "voidCount": 0, "voidSum": 0,
                            "processedRefunds": 0, "byPayment": {}, "refundsByPayment": {}}
            shifts[name] = set()
        return result[name]

    for order in orders:
        item = row(order.staff_name)
        shifts[order.staff_name].add(order.shift_id)
        if order.status == "cancelled":
            item["voidCount"] += 1
            item["voidSum"] += order.total
        else:
            item["count"] += 1
            item["revenue"] += order.total
            item["discounts"] += order.discount
            add_payment_totals(item["byPayment"], order)
    # Join once, including sales outside the report period; never expose other tenants.
    refunds = db.execute(select(OrderRefund, Order.staff_name).join(
        Order, (Order.id == OrderRefund.order_id) & (Order.company_id == OrderRefund.company_id)
    ).where(OrderRefund.company_id == cid, OrderRefund.created_at >= from_ms,
            OrderRefund.created_at < to_ms,
            *([Order.branch_id == branch_id] if branch_id is not None else []))).all()
    for refund, seller in refunds:
        item = row(seller)
        item["refunds"] += refund.amount
        item["refundsByPayment"][refund.method] = item["refundsByPayment"].get(refund.method, 0) + refund.amount
        row(refund.staff_name)["processedRefunds"] += refund.amount
    for name, item in result.items():
        item["netRevenue"] = item["revenue"] - item["refunds"]
        item["shifts"] = len(shifts[name])
    return {"from": from_ms, "to": to_ms, "branchId": branch_id,
            "rows": sorted(result.values(), key=lambda r: r["name"])}


@app.get("/api/reports/staff/me")
def my_staff_report(from_ms: int, to_ms: int, ctx: Ctx = Depends(auth)) -> dict:
    """Every role may see only its own sales, keyed by staff id (renames don't split history)."""
    if to_ms <= from_ms or to_ms - from_ms > 92 * 86400000:
        raise HTTPException(400, "Sana oralig'i 1-92 kun bo'lishi kerak")
    db, cid, sid = ctx.db, ctx.cid, ctx.staff.id
    orders = db.scalars(select(Order).where(Order.company_id == cid, Order.staff_id == sid,
                                            Order.created_at >= from_ms, Order.created_at < to_ms)).all()
    sold = [o for o in orders if o.status != "cancelled"]
    refunds = db.scalars(select(OrderRefund).where(OrderRefund.company_id == cid, OrderRefund.staff_id == sid,
                                                   OrderRefund.created_at >= from_ms,
                                                   OrderRefund.created_at < to_ms)).all()
    shifts = db.scalars(select(Shift.id).where(Shift.company_id == cid, Shift.staff_id == sid,
                                               Shift.opened_at >= from_ms, Shift.opened_at < to_ms)).all()
    revenue = sum(o.total for o in sold)
    return {"staffId": sid, "name": ctx.staff.name, "from": from_ms, "to": to_ms, "count": len(sold),
            "revenue": revenue, "discounts": sum(o.discount for o in sold),
            "average": revenue // len(sold) if sold else 0,
            "voidCount": len(orders) - len(sold), "processedRefunds": sum(r.amount for r in refunds),
            "shifts": len(shifts)}


def report_branch(ctx: Ctx, branch_id: int | None) -> int | None:
    """None = whole company (only for staff not bound to a branch)."""
    if ctx.staff.branch_id is not None:
        if branch_id is not None and branch_id != ctx.staff.branch_id:
            raise HTTPException(403, "Bu filial uchun ruxsat yo'q")
        return ctx.staff.branch_id
    if branch_id is not None:
        branch = ctx.db.get(Branch, branch_id)
        if branch is None or branch.company_id != ctx.cid:
            raise HTTPException(404, "Filial topilmadi")
    return branch_id


@app.get("/api/reports/finance")
def finance_report(days: int = 30, branchId: int | None = None, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Management P&L: sales − refunds − (COGS − returned cost) − expenses − staff payments.

    Not a statutory/tax report. Staff payments are company-wide and only included
    in the all-branches view.
    """
    days = max(1, min(days, 92))
    start = start_of_day_ms(days - 1)
    db, cid = ctx.db, ctx.cid
    branch_id = report_branch(ctx, branchId)
    order_q = select(Order).where(Order.company_id == cid, Order.created_at >= start, Order.status != "cancelled")
    expense_q = select(Expense).where(Expense.company_id == cid, Expense.created_at >= start)
    if branch_id is not None:
        order_q = order_q.where(Order.branch_id == branch_id)
        expense_q = expense_q.where(Expense.branch_id == branch_id)
    orders = db.scalars(order_q).all()
    expenses = db.scalars(expense_q).all()
    wages = [] if branch_id is not None else db.scalars(select(StaffPayment).where(
        StaffPayment.company_id == cid, StaffPayment.created_at >= start,
    )).all()
    payment_q = select(OrderPayment).join(Order, Order.id == OrderPayment.order_id).where(
        OrderPayment.company_id == cid, OrderPayment.created_at >= start, Order.status != "cancelled")
    if branch_id is not None:
        payment_q = payment_q.where(OrderPayment.branch_id == branch_id)
    collected = sum(p.amount for p in db.scalars(payment_q))
    by_payment: dict[str, int] = {}
    for o in orders:
        add_payment_totals(by_payment, o)
    refund_q = select(OrderRefund).where(OrderRefund.company_id == cid, OrderRefund.created_at >= start)
    if branch_id is not None:
        refund_q = refund_q.where(OrderRefund.order_id.in_(
            select(Order.id).where(Order.company_id == cid, Order.branch_id == branch_id)))
    refunds = db.scalars(refund_q).all()
    refunds_by_payment: dict[str, int] = {}
    for refund in refunds:
        refunds_by_payment[refund.method] = refunds_by_payment.get(refund.method, 0) + refund.amount

    daily = []
    for d in range(days - 1, -1, -1):
        lo, hi = start_of_day_ms(d), start_of_day_ms(d - 1)
        day_sales = [o for o in orders if lo <= o.created_at < hi]
        day_expenses = sum(e.amount for e in expenses if lo <= e.created_at < hi)
        day_wages = sum(w.amount for w in wages if lo <= w.created_at < hi)
        day_refunds = sum(r.amount for r in refunds if lo <= r.created_at < hi)
        revenue = sum(o.total for o in day_sales)
        cogs = sum(o.cost for o in day_sales) - sum(r.cost_reversed or 0 for r in refunds if lo <= r.created_at < hi)
        daily.append({
            "day": lo, "orders": len(day_sales), "revenue": revenue,
            "refunds": day_refunds, "netRevenue": revenue - day_refunds,
            "cogs": cogs, "grossProfit": revenue - day_refunds - cogs,
            "expenses": day_expenses, "staffPayments": day_wages,
            "operatingBalance": revenue - day_refunds - cogs - day_expenses - day_wages,
        })
    def total(key: str) -> int:
        return sum(day[key] for day in daily)
    return {
        "days": days, "start": start,
        "orders": total("orders"), "revenue": total("revenue"),
        "refunds": total("refunds"), "netRevenue": total("netRevenue"),
        "cogs": total("cogs"), "grossProfit": total("grossProfit"),
        "expenses": total("expenses"), "staffPayments": total("staffPayments"),
        "operatingBalance": total("operatingBalance"),
        "byPayment": by_payment, "refundsByPayment": refunds_by_payment, "daily": daily,
        "branchId": branch_id,
        "reconciliation": {
            "collected": collected, "refunds": total("refunds"), "netCollected": collected - total("refunds"),
            "outstanding": sum(o.total - sum(p["amount"] for p in order_payment_parts(o))
                               for o in orders if o.payment_status == "partial"),
        },
        "note": "Refunds are recorded after external confirmation; returned-to-stock cost is removed from COGS. Tax, supplier debts, pending salaries and other liabilities are not included.",
    }


@app.get("/api/reports/cash-variance")
def cash_variance_report(days: int = 30, branchId: int | None = None,
                         ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    """Closed shifts: expected = opening + cash sales − cash refunds − cash expenses."""
    days = max(1, min(days, 92))
    branch_id = report_branch(ctx, branchId)
    q = select(Shift).where(Shift.company_id == ctx.cid, Shift.closed_at.is_not(None),
                            Shift.closed_at >= start_of_day_ms(days - 1)).order_by(Shift.closed_at.desc())
    if branch_id is not None:
        q = q.where(Shift.branch_id == branch_id)
    items = []
    for shift in ctx.db.scalars(q):
        summary = shift_summary(ctx.db, shift)
        items.append({
            "shiftId": shift.id, "branchId": shift.branch_id, "openedBy": shift.staff_name,
            "closedBy": shift.closed_by, "openedAt": shift.opened_at, "closedAt": shift.closed_at,
            "openingCash": shift.opening_cash, "cashSales": summary["byPayment"].get("naqd", 0),
            "cashRefunds": summary["cashRefunds"], "cashExpenses": summary["cashExpenses"],
            "expectedCash": shift.expected_cash, "closingCash": shift.closing_cash,
            "difference": (shift.closing_cash or 0) - (shift.expected_cash or 0),
        })
    return {
        "days": days, "branchId": branch_id, "items": items,
        "shortage": sum(-i["difference"] for i in items if i["difference"] < 0),
        "surplus": sum(i["difference"] for i in items if i["difference"] > 0),
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
            "plan": subscription.plan, "status": subscription.status, "modules": subscription.modules or [],
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


def ensure_hookah_catalog(db: Session, cid: int, modules: list[str]) -> None:
    if "hookah" not in modules:
        return
    categories = rows(db, Category, cid)
    if not any(re.search(r"kalyan|кальян|hookah", c.name, re.I) for c in categories):
        category_key = "hookah"
        if any(c.key == category_key for c in categories):
            category_key += "-" + secrets.token_hex(3)
        db.add(Category(company_id=cid, key=category_key, name="Kalyan", sort=max((c.sort for c in categories), default=0) + 1))


class PlatformCompanyIn(BaseModel):
    modules: list[Literal["hookah"]] = Field(default_factory=list, max_length=1)
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
    company = create_company(db, slug, body.name.strip(), body.owner_name.strip(), body.owner_pin, profile="hookah" if "hookah" in body.modules else "coffee")
    expiry = now_ms() + body.days * 86400000
    sub = Subscription(company_id=company.id, plan=body.plan, status="active", expires_at=expiry, modules=body.modules)
    db.add(sub)
    ensure_hookah_catalog(db, company.id, body.modules)
    db.commit()
    return platform_company(company, sub)


class PlatformSubscriptionIn(BaseModel):
    modules: list[Literal["hookah"]] | None = Field(default=None, max_length=1)
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
        if body.modules is not None:
            sub.modules = body.modules
        ensure_hookah_catalog(db, company.id, sub.modules or [])
    db.commit()
    return platform_company(company, sub)


@app.get("/api/modules/hookah")
def hookah_access(ctx: Ctx = Depends(require(*CASHIERS))) -> dict:
    if "hookah" not in enabled_modules(ctx.db, ctx.cid):
        raise HTTPException(403, "Kalyanxona moduli litsenziyada yoqilmagan")
    return {"module": "hookah", "enabled": True, "branchId": ctx.branch_id}
