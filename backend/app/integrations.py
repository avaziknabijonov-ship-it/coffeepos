"""Fiscal provider gateway (fail-closed), encrypted tenant credentials and Telegram director digest."""
import base64
import hashlib
import json
import os
import re
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import record as audit_record
from .core import MANAGERS, TZ, Ctx, require
from .db import (FiscalConfig, FiscalReceipt, Order, OrderRefund, OutboxMessage, Shift, StockNotification,
                 TelegramConfig, now_ms)
from .fiscal import FiscalNotConfigured, FiscalResult, FiscalTenantConfig, issue_fiscal_receipt
from .security import secret_key

router = APIRouter()
MAX_ATTEMPTS = 5


# ---------- field encryption ----------
def _fernet(db: Session) -> Fernet:
    """FIELD_ENCRYPTION_KEY (Fernet key) wins; otherwise a key derived from the app secret."""
    env = os.environ.get("FIELD_ENCRYPTION_KEY")
    if env:
        return Fernet(env.encode())
    digest = hashlib.sha256((secret_key(db) + ":field-encryption:v1").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(db: Session, value: str) -> str:
    return _fernet(db).encrypt(value.encode()).decode()


def decrypt(db: Session, value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet(db).decrypt(value.encode()).decode()
    except InvalidToken:
        raise RuntimeError("Encrypted credential cannot be decrypted with the configured key") from None


# ---------- fiscal ----------
class SandboxProvider:
    """Deterministic test double; its receipts are never shown as fiscal."""
    name = "sandbox"

    def issue_receipt(self, *, tenant: FiscalTenantConfig, order_id: int, idempotency_key: str) -> FiscalResult:
        sign = hashlib.sha256(f"{tenant.tin}:{tenant.terminal_id}:{idempotency_key}".encode()).hexdigest()[:20]
        return FiscalResult(f"SBX-{order_id}-{sign[:8]}", sign,
                            f"https://sandbox.invalid/check?t={tenant.terminal_id}&r={order_id}&s={sign}")


PROVIDERS: dict[str, Callable[[], object]] = {"sandbox": SandboxProvider}


def fiscal_config(db: Session, cid: int) -> FiscalConfig:
    config = db.get(FiscalConfig, cid)
    if config is None:
        config = FiscalConfig(company_id=cid)
        db.add(config)
        db.flush()
    return config


def fiscalize(db: Session, cid: int, order_id: int, amount: int, kind: str, key: str,
              refund_id: int | None = None) -> str:
    """Return the receipt status. Mandatory mode fails closed (HTTP 503) and blocks the sale."""
    config = db.get(FiscalConfig, cid)
    if config is None or not config.enabled:
        return "nonfiscal"
    existing = db.scalar(select(FiscalReceipt).where(FiscalReceipt.company_id == cid,
                                                     FiscalReceipt.idempotency_key == key))
    if existing is not None:
        return existing.status
    factory = PROVIDERS.get(config.provider)
    tenant = FiscalTenantConfig(cid, config.tin, config.provider, config.terminal_id, config.enabled)
    try:
        result = issue_fiscal_receipt(tenant=tenant, order_id=order_id, idempotency_key=key,
                                      provider=factory() if factory else None)
    except (FiscalNotConfigured, RuntimeError, ValueError) as exc:
        if config.mandatory:
            raise HTTPException(503, "Fiskal provayder mavjud emas: savdo bloklandi") from exc
        return "nonfiscal"
    status = "sandbox" if config.provider == "sandbox" else "issued"
    db.add(FiscalReceipt(company_id=cid, order_id=order_id, refund_id=refund_id, kind=kind, status=status,
                         provider=config.provider, idempotency_key=key, provider_receipt_id=result.provider_receipt_id,
                         fiscal_sign=result.fiscal_sign, qr_payload=result.qr_payload, amount=amount))
    return status


def sale_receipt(db: Session, cid: int, order_id: int) -> FiscalReceipt | None:
    return db.scalar(select(FiscalReceipt).where(FiscalReceipt.company_id == cid, FiscalReceipt.order_id == order_id,
                                                 FiscalReceipt.kind == "sale"))


class FiscalConfigIn(BaseModel):
    tin: str = Field(pattern=r"^\d{9}$")
    provider: str = Field(min_length=1, max_length=32)
    terminalId: str = Field(min_length=1, max_length=64)
    operator: str = Field(default="", max_length=64)
    enabled: bool = False
    mandatory: bool = False
    credentials: str | None = Field(default=None, max_length=4096)


def fiscal_out(c: FiscalConfig) -> dict:
    return {"tin": c.tin, "provider": c.provider, "terminalId": c.terminal_id, "operator": c.operator,
            "enabled": c.enabled, "mandatory": c.mandatory, "hasCredentials": bool(c.credentials_enc),
            "providers": sorted(PROVIDERS), "certified": c.provider in PROVIDERS and c.provider != "sandbox"}


@router.get("/api/fiscal/config")
def get_fiscal_config(ctx: Ctx = Depends(require("owner"))) -> dict:
    return fiscal_out(fiscal_config(ctx.db, ctx.cid))


@router.put("/api/fiscal/config")
def put_fiscal_config(body: FiscalConfigIn, ctx: Ctx = Depends(require("owner"))) -> dict:
    if body.enabled and body.provider not in PROVIDERS:
        raise HTTPException(422, "Bu provayder uchun adapter yo‘q")
    if body.mandatory and not body.enabled:
        raise HTTPException(422, "Majburiy rejim uchun fiskal yoqilgan bo‘lishi kerak")
    config = fiscal_config(ctx.db, ctx.cid)
    before = {"status": "enabled" if config.enabled else "disabled"}
    config.tin, config.provider, config.terminal_id = body.tin, body.provider, body.terminalId
    config.operator, config.enabled, config.mandatory = body.operator.strip(), body.enabled, body.mandatory
    if body.credentials is not None:
        config.credentials_enc = encrypt(ctx.db, body.credentials) if body.credentials else None
    config.updated_at = now_ms()
    audit_record(ctx, "fiscal.config", ctx.cid, before, {"status": "enabled" if body.enabled else "disabled"})
    ctx.db.commit()
    return fiscal_out(config)


@router.get("/api/orders/{oid}/fiscal")
def order_fiscal(oid: int, ctx: Ctx = Depends(require(*MANAGERS))) -> dict:
    receipts = ctx.db.scalars(select(FiscalReceipt).where(FiscalReceipt.company_id == ctx.cid,
                                                          FiscalReceipt.order_id == oid)).all()
    return {"orderId": oid, "items": [{"kind": r.kind, "status": r.status, "provider": r.provider,
                                       "receiptId": r.provider_receipt_id, "sign": r.fiscal_sign,
                                       "qr": r.qr_payload, "amount": r.amount, "refundId": r.refund_id,
                                       "createdAt": r.created_at} for r in receipts]}


# ---------- Telegram director digest ----------
def day_bounds(day: str) -> tuple[int, int]:
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TZ)
    return int(start.timestamp() * 1000), int((start + timedelta(days=1)).timestamp() * 1000)


def digest_text(db: Session, cid: int, day: str) -> str:
    start, end = day_bounds(day)
    orders = db.scalars(select(Order).where(Order.company_id == cid, Order.created_at >= start,
                                            Order.created_at < end, Order.status != "cancelled")).all()
    refunds = db.scalar(select(func.coalesce(func.sum(OrderRefund.amount), 0)).where(
        OrderRefund.company_id == cid, OrderRefund.created_at >= start, OrderRefund.created_at < end))
    shifts = db.scalars(select(Shift).where(Shift.company_id == cid, Shift.closed_at.is_not(None),
                                            Shift.closed_at >= start, Shift.closed_at < end)).all()
    variance = sum((s.closing_cash or 0) - (s.expected_cash or 0) for s in shifts)
    low = db.scalar(select(func.count(StockNotification.id)).where(
        StockNotification.company_id == cid, StockNotification.resolved_at.is_(None)))
    revenue = sum(o.total for o in orders)
    money = lambda v: f"{int(v):,}".replace(",", " ")
    # Aggregates only: no customer phones/names or staff PINs leave the system.
    return (f"CoffeePOS {day}\nSavdo / Выручка: {money(revenue)} UZS\nBuyurtmalar / Заказы: {len(orders)}\n"
            f"Qaytarish / Возвраты: {money(refunds)} UZS\nKassa farqi / Разница кассы: {money(variance)} UZS\n"
            f"Kam qoldiq / Мало на складе: {low}")


def enqueue_digest(db: Session, cid: int, day: str) -> OutboxMessage | None:
    config = db.get(TelegramConfig, cid)
    if config is None or not config.enabled:
        return None
    key = f"digest:{day}"
    existing = db.scalar(select(OutboxMessage).where(OutboxMessage.company_id == cid, OutboxMessage.dedupe_key == key))
    if existing is not None:
        return existing
    message = OutboxMessage(company_id=cid, channel="telegram", kind="daily_digest", dedupe_key=key,
                            text=digest_text(db, cid, day))
    try:
        with db.begin_nested():
            db.add(message)
    except IntegrityError:
        return db.scalar(select(OutboxMessage).where(OutboxMessage.company_id == cid,
                                                     OutboxMessage.dedupe_key == key))
    return message


def telegram_send(token: str, chat_id: str, text: str) -> None:
    data = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - fixed https host
        if resp.status != 200:
            raise RuntimeError(f"Telegram HTTP {resp.status}")


Sender = Callable[[str, str, str], None]


def dispatch(db: Session, cid: int | None = None, sender: Sender = telegram_send, now: int | None = None) -> dict:
    """Deliver due messages; failures back off 1, 2, 4, 8 min and stop after MAX_ATTEMPTS."""
    now = now or now_ms()
    q = select(OutboxMessage).where(OutboxMessage.status == "pending", OutboxMessage.next_attempt_at <= now)
    if cid is not None:
        q = q.where(OutboxMessage.company_id == cid)
    sent = failed = 0
    for message in db.scalars(q.with_for_update(skip_locked=True).limit(100)).all():
        config = db.get(TelegramConfig, message.company_id)
        try:
            if config is None or not config.enabled or not config.chat_id or not config.token_enc:
                raise RuntimeError("Telegram is not configured")
            sender(decrypt(db, config.token_enc), config.chat_id, message.text)
            message.status, message.sent_at = "sent", now
            sent += 1
        except Exception as exc:  # noqa: BLE001 - any delivery failure is retried
            message.attempts += 1
            message.last_error = re.sub(r"bot[0-9]+:[A-Za-z0-9_-]+", "bot***", str(exc))[:200]
            if message.attempts >= MAX_ATTEMPTS:
                message.status = "failed"
            else:
                message.next_attempt_at = now + 60_000 * 2 ** (message.attempts - 1)
            failed += 1
    db.commit()
    return {"sent": sent, "failed": failed}


class TelegramIn(BaseModel):
    enabled: bool
    chatId: str = Field(default="", pattern=r"^-?[0-9]{0,20}$")
    token: str | None = Field(default=None, pattern=r"^([0-9]{5,12}:[A-Za-z0-9_-]{20,64})?$")


def telegram_out(c: TelegramConfig) -> dict:
    return {"enabled": c.enabled, "chatId": c.chat_id, "hasToken": bool(c.token_enc)}


@router.get("/api/telegram/config")
def get_telegram(ctx: Ctx = Depends(require("owner"))) -> dict:
    return telegram_out(ctx.db.get(TelegramConfig, ctx.cid) or TelegramConfig(company_id=ctx.cid, enabled=False))


@router.put("/api/telegram/config")
def put_telegram(body: TelegramIn, ctx: Ctx = Depends(require("owner"))) -> dict:
    config = ctx.db.get(TelegramConfig, ctx.cid)
    if config is None:
        config = TelegramConfig(company_id=ctx.cid)
        ctx.db.add(config)
    if body.token is not None:
        config.token_enc = encrypt(ctx.db, body.token) if body.token else None
    if body.enabled and (not body.chatId or not config.token_enc):
        raise HTTPException(422, "Chat ID va bot token kerak")
    config.enabled, config.chat_id, config.updated_at = body.enabled, body.chatId, now_ms()
    audit_record(ctx, "telegram.config", ctx.cid, {}, {"status": "enabled" if body.enabled else "disabled"})
    ctx.db.commit()
    return telegram_out(config)


class DigestIn(BaseModel):
    day: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


@router.post("/api/telegram/digest")
def run_digest(body: DigestIn, ctx: Ctx = Depends(require("owner"))) -> dict:
    day = body.day or datetime.now(TZ).strftime("%Y-%m-%d")
    message = enqueue_digest(ctx.db, ctx.cid, day)
    if message is None:
        raise HTTPException(409, "Telegram hisobot yoqilmagan")
    ctx.db.commit()
    return outbox_out(message)


def outbox_out(m: OutboxMessage) -> dict:
    return {"id": m.id, "kind": m.kind, "key": m.dedupe_key, "status": m.status, "attempts": m.attempts,
            "nextAttemptAt": m.next_attempt_at, "lastError": m.last_error, "sentAt": m.sent_at, "text": m.text}


@router.get("/api/telegram/outbox")
def list_outbox(ctx: Ctx = Depends(require("owner"))) -> list[dict]:
    q = select(OutboxMessage).where(OutboxMessage.company_id == ctx.cid).order_by(OutboxMessage.id.desc()).limit(50)
    return [outbox_out(m) for m in ctx.db.scalars(q)]


@router.post("/api/telegram/dispatch")
def dispatch_now(ctx: Ctx = Depends(require("owner"))) -> dict:
    return dispatch(ctx.db, ctx.cid)


def main() -> None:
    """Cron entry point: `python -m app.integrations` enqueues yesterday's digests and dispatches."""
    from .db import Company, SessionLocal
    day = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    with SessionLocal() as db:
        for cid in db.scalars(select(Company.id)):
            enqueue_digest(db, cid, day)
        db.commit()
        print(dispatch(db))


if __name__ == "__main__":
    main()
