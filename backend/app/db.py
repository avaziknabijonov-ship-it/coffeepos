import os
import time

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def _default_url() -> str:
    if os.path.isdir("/data"):
        return "sqlite:////data/coffeepos.db"
    return "sqlite:///./coffeepos.db"


DATABASE_URL = os.environ.get("DATABASE_URL") or _default_url()
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def now_ms() -> int:
    return int(time.time() * 1000)


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512))


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Branch(Base):
    """A physical point of sale; every company has exactly one default branch."""
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("company_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class BranchStock(Base):
    """Stock of non-default branches; the default branch keeps Ingredient.stock/min."""
    __tablename__ = "branch_stock"
    __table_args__ = (UniqueConstraint("company_id", "branch_id", "ingredient"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    ingredient: Mapped[str] = mapped_column(String(64))
    qty: Mapped[float] = mapped_column(default=0)
    min: Mapped[float] = mapped_column(default=0)


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))
    pin_hash: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_barista: Mapped[bool] = mapped_column(Boolean, default=False)
    can_cancel_orders: Mapped[bool] = mapped_column(Boolean, default=False)
    can_reprint_receipts: Mapped[bool] = mapped_column(Boolean, default=False)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("company_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64))
    image_url: Mapped[str] = mapped_column(String(512), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Ingredient(Base):
    __tablename__ = "ingredients"
    __table_args__ = (UniqueConstraint("company_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    unit: Mapped[str] = mapped_column(String(8))
    cost: Mapped[float] = mapped_column(default=0)
    stock: Mapped[float] = mapped_column(default=0)
    min: Mapped[float] = mapped_column(default=0)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("company_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    cat: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    combo_components: Mapped[list | None] = mapped_column(JSON, nullable=True)
    image_url: Mapped[str] = mapped_column(String(512), default="")
    mods: Mapped[list] = mapped_column(JSON, default=list)
    sizes: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Modifier(Base):
    __tablename__ = "modifiers"
    __table_args__ = (UniqueConstraint("company_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    group: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(64))
    price: Mapped[int] = mapped_column(BigInteger, default=0)
    effect: Mapped[dict] = mapped_column(JSON, default=dict)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    staff_name: Mapped[str] = mapped_column(String(64))
    opened_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    opening_cash: Mapped[int] = mapped_column(BigInteger, default=0)
    closed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closing_cash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expected_cash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("company_id", "client_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    client_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    number: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(500), default="")
    guest_count: Mapped[int] = mapped_column(Integer, default=1)
    waiter_name: Mapped[str] = mapped_column(String(64), default="")
    customer: Mapped[str] = mapped_column(String(64), default="")
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    bonus_used: Mapped[int] = mapped_column(BigInteger, default=0)
    bonus_earned: Mapped[int] = mapped_column(BigInteger, default=0)
    items: Mapped[list] = mapped_column(JSON)
    subtotal: Mapped[int] = mapped_column(BigInteger)
    discount: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger)
    cost: Mapped[int] = mapped_column(BigInteger)
    payment: Mapped[str] = mapped_column(String(16))
    payment_parts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    payment_status: Mapped[str] = mapped_column(String(16), default="paid")
    service: Mapped[str | None] = mapped_column(String(16), nullable=True)
    table_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fiscal_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    promotion_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cash_given: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="new")
    cancelled_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)
    ready_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    staff_name: Mapped[str] = mapped_column(String(64))


class StockMove(Base):
    __tablename__ = "stock_moves"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ingredient: Mapped[str] = mapped_column(String(64))
    qty: Mapped[float] = mapped_column()
    reason: Mapped[str] = mapped_column(String(16))
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staff_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)
    note: Mapped[str | None] = mapped_column(String(32), nullable=True)
    inventory_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Inventory(Base):
    """A stocktake: counted vs. expected quantities for a set of ingredients."""

    __tablename__ = "inventories"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="approved")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    staff_name: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(String(200), default="")
    lines: Mapped[list] = mapped_column(JSON)
    shortage: Mapped[int] = mapped_column(BigInteger, default=0)
    surplus: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)


class PurchaseInvoice(Base):
    """Supplier delivery note; lines preserve purchase prices and units."""
    __tablename__ = "purchase_invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    number: Mapped[str] = mapped_column(String(64))
    supplier: Mapped[str] = mapped_column(String(128))
    received_at: Mapped[int] = mapped_column(BigInteger)
    payment_status: Mapped[str] = mapped_column(String(16), default="unpaid")
    status: Mapped[str] = mapped_column(String(16), default="active")
    cancelled_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    lines: Mapped[list] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    staff_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint("company_id", "number"),)


class Subscription(Base):
    __tablename__ = "subscriptions"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    modules: Mapped[list] = mapped_column(JSON, default=list)
    plan: Mapped[str] = mapped_column(String(16), default="monthly")
    status: Mapped[str] = mapped_column(String(16), default="active")
    expires_at: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256), default="")
    payment: Mapped[str] = mapped_column(String(16), default="cash")
    staff_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)


class StaffPayment(Base):
    __tablename__ = "staff_payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(String(256), default="")
    recorded_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)

class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("company_id", "phone"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    phone: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(64), default="")
    bonus_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    analytics_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_updated_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    consent_actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erased_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class BonusConfig(Base):
    __tablename__ = "bonus_configs"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    earn_percent: Mapped[int] = mapped_column(Integer, default=5)
    redemption_limit_percent: Mapped[int] = mapped_column(Integer, default=30)


class BonusLedger(Base):
    __tablename__ = "bonus_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)

class PayrollPlan(Base):
    """Staff workdays and monthly salary set by a manager for a specific month."""
    __tablename__ = "payroll_plans"
    __table_args__ = (UniqueConstraint("company_id", "staff_id", "month"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    month: Mapped[str] = mapped_column(String(7))
    monthly_salary: Mapped[int] = mapped_column(BigInteger, default=0)
    standard_days: Mapped[int] = mapped_column(Integer, default=26)
    worked_days: Mapped[float] = mapped_column(default=0)
    deductions: Mapped[int] = mapped_column(BigInteger, default=0)
    note: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class DraftOrder(Base):
    """Parked cart; never counted as a sale and never reserves stock."""
    __tablename__ = "draft_orders"
    __table_args__ = (UniqueConstraint("company_id", "client_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    client_key: Mapped[str] = mapped_column(String(64))
    items: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(String(500), default="")
    guest_count: Mapped[int] = mapped_column(Integer, default=1)
    waiter_name: Mapped[str] = mapped_column(String(64), default="")
    customer: Mapped[str] = mapped_column(String(64), default="")
    table_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    service: Mapped[str] = mapped_column(String(16), default="takeaway")
    staff_name: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class OrderRefund(Base):
    """Recorded refunds only: external gateway transfer is never initiated here."""
    __tablename__ = "order_refunds"
    __table_args__ = (UniqueConstraint("company_id", "client_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    client_key: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(256))
    staff_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    restocked: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_reversed: Mapped[int] = mapped_column(BigInteger, default=0)
    bonus_reversed: Mapped[int] = mapped_column(BigInteger, default=0)
    bonus_restored: Mapped[int] = mapped_column(BigInteger, default=0)
    fiscal_status: Mapped[str] = mapped_column(String(16), default="nonfiscal")


class OrderPayment(Base):
    """One captured tender; client_key blocks duplicates from retries or a second device."""
    __tablename__ = "order_payments"
    __table_args__ = (UniqueConstraint("company_id", "client_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    shift_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(BigInteger)
    client_key: Mapped[str] = mapped_column(String(80))
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staff_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)


class AuditEvent(Base):
    """Append-only operational audit; sensitive free text is deliberately excluded."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_id: Mapped[int] = mapped_column(Integer)
    actor_name: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[int] = mapped_column(Integer)
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)


class Promotion(Base):
    __tablename__ = 'promotions'
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), index=True)
    name: Mapped[str] = mapped_column(String(64))
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    weekdays: Mapped[list] = mapped_column(JSON)
    percent: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_discount: Mapped[int] = mapped_column(BigInteger, default=0)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ReceiptLink(Base):
    """Revocable receipt grants; bearer tokens are never stored."""
    __tablename__ = 'receipt_links'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class StockNotification(Base):
    """Low-stock episode; open_key is unique while open, so one alert per episode."""
    __tablename__ = "stock_notifications"
    __table_args__ = (UniqueConstraint("company_id", "open_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    ingredient: Mapped[str] = mapped_column(String(64))
    open_key: Mapped[str | None] = mapped_column(String(96), nullable=True)
    stock: Mapped[float] = mapped_column(default=0)
    min: Mapped[float] = mapped_column(default=0)
    opened_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)
    resolved_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class StockTransfer(Base):
    """Branch-to-branch movement: dispatched (in transit) -> received | cancelled."""
    __tablename__ = "stock_transfers"
    __table_args__ = (UniqueConstraint("company_id", "client_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    client_key: Mapped[str] = mapped_column(String(64))
    from_branch_id: Mapped[int] = mapped_column(Integer, index=True)
    to_branch_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(16), default="in_transit")
    lines: Mapped[list] = mapped_column(JSON)
    received_lines: Mapped[list | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="")
    dispatched_by: Mapped[str] = mapped_column(String(64))
    dispatched_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)
    closed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class DiningArea(Base):
    __tablename__ = "dining_areas"
    __table_args__ = (UniqueConstraint("company_id", "branch_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DiningTable(Base):
    __tablename__ = "dining_tables"
    __table_args__ = (UniqueConstraint("company_id", "branch_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int] = mapped_column(Integer, index=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("dining_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    seats: Mapped[int] = mapped_column(Integer, default=2)
    layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    layout_version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class FiscalConfig(Base):
    """Per-company fiscal settings; provider credentials are stored encrypted only."""
    __tablename__ = "fiscal_configs"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    tin: Mapped[str] = mapped_column(String(9), default="")
    provider: Mapped[str] = mapped_column(String(32), default="")
    terminal_id: Mapped[str] = mapped_column(String(64), default="")
    operator: Mapped[str] = mapped_column(String(64), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    credentials_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class FiscalReceipt(Base):
    __tablename__ = "fiscal_receipts"
    __table_args__ = (UniqueConstraint("company_id", "idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    order_id: Mapped[int] = mapped_column(Integer, index=True)
    refund_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(96))
    provider_receipt_id: Mapped[str] = mapped_column(String(128), default="")
    fiscal_sign: Mapped[str] = mapped_column(String(128), default="")
    qr_payload: Mapped[str] = mapped_column(String(512), default="")
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class TelegramConfig(Base):
    """Opt-in director digest; bot token is per tenant and encrypted at rest."""
    __tablename__ = "telegram_configs"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_id: Mapped[str] = mapped_column(String(64), default="")
    token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class OutboxMessage(Base):
    """At-least-once notification outbox with bounded exponential retry."""
    __tablename__ = "outbox_messages"
    __table_args__ = (UniqueConstraint("company_id", "dedupe_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(32))
    dedupe_key: Mapped[str] = mapped_column(String(96))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    last_error: Mapped[str] = mapped_column(String(200), default="")
    sent_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Device(Base):
    """Registered POS/KDS/APK device; only a hash of its secret is stored."""
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    app_version: Mapped[str] = mapped_column(String(32), default="")
    last_seen_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    revoked_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class DevicePolicy(Base):
    __tablename__ = "device_policies"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    require_device: Mapped[bool] = mapped_column(Boolean, default=False)


class AppRelease(Base):
    """Platform-wide client release with staged rollout and rollback."""
    __tablename__ = "app_releases"
    __table_args__ = (UniqueConstraint("platform", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(16))
    version: Mapped[str] = mapped_column(String(32))
    min_backend: Mapped[str] = mapped_column(String(32), default="0.0.0")
    min_supported: Mapped[str] = mapped_column(String(32), default="0.0.0")
    rollout_percent: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    url: Mapped[str] = mapped_column(String(512), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class OfflineConflict(Base):
    """Offline sale the server could not accept as-is; kept for manager review, never auto-dropped."""
    __tablename__ = "offline_conflicts"
    __table_args__ = (UniqueConstraint("company_id", "client_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_key: Mapped[str] = mapped_column(String(64))
    body: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="open")
    staff_name: Mapped[str] = mapped_column(String(64))
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
