import os
import time

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint, create_engine
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


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))
    pin_hash: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("company_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64))
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
    staff_name: Mapped[str] = mapped_column(String(64))
    opened_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    opening_cash: Mapped[int] = mapped_column(BigInteger, default=0)
    closed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closing_cash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expected_cash: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    customer: Mapped[str] = mapped_column(String(64), default="")
    items: Mapped[list] = mapped_column(JSON)
    subtotal: Mapped[int] = mapped_column(BigInteger)
    discount: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger)
    cost: Mapped[int] = mapped_column(BigInteger)
    payment: Mapped[str] = mapped_column(String(16))
    cash_given: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="new")
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)
    ready_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    staff_name: Mapped[str] = mapped_column(String(64))


class StockMove(Base):
    __tablename__ = "stock_moves"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
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
    staff_name: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(String(200), default="")
    lines: Mapped[list] = mapped_column(JSON)
    shortage: Mapped[int] = mapped_column(BigInteger, default=0)
    surplus: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)


class Subscription(Base):
    """Tenant subscription state; billing and enforcement are not implemented yet."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("company_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="trial", nullable=False)
    trial_ends_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_period_ends_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    grace_ends_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, nullable=False)
