"""Versioned, idempotent schema migrations (recorded in schema_migrations).

create_all() creates new tables; steps here alter tables that may already exist
in deployed databases. Every step must be safe to re-run.
"""
from sqlalchemy import inspect, select, text

from .db import Branch, Company, SessionLocal

def legacy_columns(engine) -> None:
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
    if "combo_components" not in product_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE products ADD COLUMN combo_components JSON"))
    if "image_url" not in product_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE products ADD COLUMN image_url VARCHAR(512) NOT NULL DEFAULT ''"))
    customer_columns = {c["name"] for c in inspect(engine).get_columns("customers")}
    with engine.begin() as conn:
        if "analytics_consent" not in customer_columns:
            conn.execute(text("ALTER TABLE customers ADD COLUMN analytics_consent BOOLEAN NOT NULL DEFAULT FALSE"))
        if "consent_updated_at" not in customer_columns:
            conn.execute(text("ALTER TABLE customers ADD COLUMN consent_updated_at BIGINT"))
        if "consent_actor_id" not in customer_columns:
            conn.execute(text("ALTER TABLE customers ADD COLUMN consent_actor_id INTEGER"))
    order_columns = {c["name"] for c in inspect(engine).get_columns("orders")}
    with engine.begin() as conn:
        if "promotion_snapshot" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN promotion_snapshot JSON"))
        if "payment_parts" not in order_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN payment_parts JSON"))
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




BRANCH_COLUMNS = {
    "staff": ["branch_id INTEGER"],
    "shifts": ["branch_id INTEGER", "staff_id INTEGER"],
    "orders": ["branch_id INTEGER", "staff_id INTEGER"],
    "stock_moves": ["branch_id INTEGER"],
    "expenses": ["branch_id INTEGER"],
    "draft_orders": ["branch_id INTEGER"],
    "order_refunds": ["staff_id INTEGER"],
    "audit_events": ["branch_id INTEGER"],
}


def add_columns(engine, spec: dict[str, list[str]]) -> None:
    for table, columns in spec.items():
        have = {c["name"] for c in inspect(engine).get_columns(table)}
        with engine.begin() as conn:
            for column in columns:
                if column.split()[0] not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column}"))


def branches_and_attribution(engine) -> None:
    add_columns(engine, BRANCH_COLUMNS)
    with SessionLocal() as db:
        for company in db.scalars(select(Company)):
            if not db.scalar(select(Branch.id).where(Branch.company_id == company.id, Branch.is_default.is_(True))):
                db.add(Branch(company_id=company.id, name="Asosiy filial", is_default=True))
        db.commit()
    with engine.begin() as conn:
        # audit_events is append-only; pre-branch events keep branch_id NULL.
        for table in ("shifts", "orders", "stock_moves", "expenses", "draft_orders"):
            conn.execute(text(f"UPDATE {table} SET branch_id = (SELECT b.id FROM branches b WHERE b.company_id = {table}.company_id AND b.is_default = TRUE) WHERE branch_id IS NULL"))
        for table, name_col in (("orders", "staff_name"), ("shifts", "staff_name"), ("order_refunds", "staff_name")):
            # Backfill only when the historical name is unambiguous inside the company.
            conn.execute(text(f"""UPDATE {table} SET staff_id = (SELECT MIN(s.id) FROM staff s
                WHERE s.company_id = {table}.company_id AND s.name = {table}.{name_col})
                WHERE staff_id IS NULL AND (SELECT COUNT(*) FROM staff s
                WHERE s.company_id = {table}.company_id AND s.name = {table}.{name_col}) = 1"""))


def payments_and_refund_reversals(engine) -> None:
    add_columns(engine, {
        "orders": ["payment_status VARCHAR(16) DEFAULT 'paid'"],
        "order_refunds": ["items JSON", "restocked BOOLEAN DEFAULT FALSE", "cost_reversed BIGINT DEFAULT 0",
                          "bonus_reversed BIGINT DEFAULT 0", "fiscal_status VARCHAR(16) DEFAULT 'nonfiscal'"],
    })
    with engine.begin() as conn:
        conn.execute(text("UPDATE orders SET payment_status = 'paid' WHERE payment_status IS NULL"))
        legacy = conn.execute(text("""SELECT o.id, o.company_id, o.branch_id, o.shift_id, o.payment, o.total,
            o.payment_parts, o.staff_id, o.staff_name, o.created_at FROM orders o
            WHERE NOT EXISTS (SELECT 1 FROM order_payments p WHERE p.order_id = o.id)""")).all()
        for row in legacy:
            parts = row.payment_parts
            if isinstance(parts, str):
                parts = __import__("json").loads(parts)
            for index, part in enumerate(parts or [{"method": row.payment, "amount": row.total}]):
                conn.execute(text("""INSERT INTO order_payments (company_id, branch_id, order_id, shift_id, method,
                    amount, client_key, staff_id, staff_name, created_at) VALUES (:c, :b, :o, :s, :m, :a, :k, :sid, :n, :t)"""),
                    {"c": row.company_id, "b": row.branch_id, "o": row.id, "s": row.shift_id, "m": part["method"],
                     "a": part["amount"], "k": f"legacy-{row.id}-{index}", "sid": row.staff_id, "n": row.staff_name,
                     "t": row.created_at})


def inventory_approval(engine) -> None:
    add_columns(engine, {"inventories": ["branch_id INTEGER", "staff_id INTEGER",
                                         "status VARCHAR(16) DEFAULT 'approved'",
                                         "approved_by VARCHAR(64)", "approved_at BIGINT"]})
    with engine.begin() as conn:
        conn.execute(text("UPDATE inventories SET status = 'approved' WHERE status IS NULL"))
        conn.execute(text("UPDATE inventories SET branch_id = (SELECT b.id FROM branches b WHERE b.company_id = inventories.company_id AND b.is_default = TRUE) WHERE branch_id IS NULL"))


def experience_columns(engine) -> None:
    add_columns(engine, {
        "promotions": ["max_discount BIGINT DEFAULT 0", "branch_id INTEGER"],
        "customers": ["erased_at BIGINT"],
        "draft_orders": ["table_id INTEGER", "service VARCHAR(16) DEFAULT 'takeaway'"],
        "orders": ["service VARCHAR(16)", "table_name VARCHAR(64)"],
        "order_refunds": ["bonus_restored BIGINT DEFAULT 0"],
    })
    with engine.begin() as conn:
        conn.execute(text("UPDATE promotions SET max_discount = 0 WHERE max_discount IS NULL"))
        conn.execute(text("UPDATE draft_orders SET service = 'takeaway' WHERE service IS NULL"))
        conn.execute(text("UPDATE order_refunds SET bonus_restored = 0 WHERE bonus_restored IS NULL"))


def fiscal_status_column(engine) -> None:
    add_columns(engine, {"orders": ["fiscal_status VARCHAR(16)"]})


def category_images(engine) -> None:
    add_columns(engine, {"categories": ["image_url VARCHAR(512) NOT NULL DEFAULT ''"]})


MIGRATIONS = [
    (1, "legacy additive columns", legacy_columns),
    (2, "branches and staff attribution", branches_and_attribution),
    (3, "payments table and refund reversals", payments_and_refund_reversals),
    (4, "branch inventory approval", inventory_approval),
    (5, "tables, happy hour caps, loyalty restore, customer erasure", experience_columns),
    (6, "order fiscal status", fiscal_status_column),
    (7, "category images", category_images),
]


def run(engine) -> list[int]:
    """Apply pending steps in order; returns versions applied in this call."""
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name VARCHAR(128) NOT NULL, applied_at BIGINT NOT NULL)"))
        done = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}
    applied = []
    for version, name, step in MIGRATIONS:
        if version in done:
            continue
        step(engine)
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO schema_migrations (version, name, applied_at) VALUES (:v, :n, :t)"),
                         {"v": version, "n": name, "t": __import__("time").time_ns() // 1_000_000})
        applied.append(version)
    return applied
