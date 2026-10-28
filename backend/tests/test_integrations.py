"""G4: fiscal config with encrypted credentials, fail-closed mandatory mode, sandbox receipts, Telegram outbox."""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from helpers import LATTE, new_company, staff_login
from test_api import app
from app import integrations
from app.db import FiscalConfig, OutboxMessage, SessionLocal

FISCAL = {"tin": "123456789", "provider": "sandbox", "terminalId": "T-1", "operator": "Kassa 1",
          "enabled": True, "mandatory": False, "credentials": "api-secret-value"}


def test_fiscal_config_encrypts_credentials_and_owner_only():
    with TestClient(app) as c:
        h, slug = new_company(c, "fis")
        admin, _ = staff_login(c, h, slug, "admin", "2468")
        assert c.put("/api/fiscal/config", headers=admin, json=FISCAL).status_code == 403
        assert c.put("/api/fiscal/config", headers=h, json={**FISCAL, "tin": "12"}).status_code == 422
        assert c.put("/api/fiscal/config", headers=h, json={**FISCAL, "provider": "unknown"}).status_code == 422
        saved = c.put("/api/fiscal/config", headers=h, json=FISCAL).json()
        assert saved["hasCredentials"] is True and "api-secret-value" not in str(saved)
        assert saved["certified"] is False
        with SessionLocal() as db:
            row = db.scalars(select(FiscalConfig)).all()
            enc = [r.credentials_enc for r in row if r.credentials_enc][-1]
            assert "api-secret-value" not in enc and integrations.decrypt(db, enc) == "api-secret-value"
        audit = c.get("/api/audit?action=fiscal.config", headers=h).json()["items"]
        assert "api-secret-value" not in str(audit)


def test_sandbox_receipt_is_never_shown_as_fiscal_and_refund_is_fiscalized():
    with TestClient(app) as c:
        h, _ = new_company(c, "sbx")
        assert c.put("/api/fiscal/config", headers=h, json=FISCAL).status_code == 200
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        order = c.post("/api/orders", headers=h, json={**LATTE, "payment": "karta"}).json()
        assert order["fiscalStatus"] == "sandbox"
        refund = c.post(f"/api/orders/{order['id']}/refunds", headers=h, json={
            "clientKey": uuid4().hex, "amount": 1000, "method": "karta", "reason": "Qaytarildi",
            "externalConfirmed": True}).json()
        assert refund["fiscalStatus"] == "sandbox"
        kinds = {r["kind"] for r in c.get(f"/api/orders/{order['id']}/fiscal", headers=h).json()["items"]}
        assert kinds == {"sale", "refund"}
        link = c.post(f"/api/orders/{order['id']}/receipt-link", headers=h).json()
        html = c.get(link["path"]).text
        assert "SANDBOX" in html and "FISKAL CHEK EMAS" in html


def test_mandatory_fiscal_without_certified_provider_blocks_sale():
    with TestClient(app) as c:
        h, _ = new_company(c, "mand")
        assert c.put("/api/fiscal/config", headers=h, json={**FISCAL, "mandatory": True}).status_code == 200
        with SessionLocal() as db:  # simulate a configured but unavailable provider
            for row in db.scalars(select(FiscalConfig).where(FiscalConfig.provider == "sandbox",
                                                             FiscalConfig.mandatory.is_(True))):
                row.provider = "offline-provider"
            db.commit()
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        blocked = c.post("/api/orders", headers=h, json=LATTE)
        assert blocked.status_code == 503
        assert c.get("/api/reports/finance?days=1", headers=h).json()["revenue"] == 0


def test_telegram_digest_opt_in_dedupe_retry_and_no_token_leak():
    with TestClient(app) as c:
        h, _ = new_company(c, "tg")
        assert c.post("/api/telegram/digest", headers=h, json={}).status_code == 409  # opt-in only
        token = "123456789:" + "A" * 35
        assert c.put("/api/telegram/config", headers=h, json={"enabled": True, "chatId": "-100123"}).status_code == 422
        saved = c.put("/api/telegram/config", headers=h, json={"enabled": True, "chatId": "-100123",
                                                              "token": token}).json()
        assert saved == {"enabled": True, "chatId": "-100123", "hasToken": True}
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        c.post("/api/orders", headers=h, json={**LATTE, "customerPhone": "+998901234567"})
        first = c.post("/api/telegram/digest", headers=h, json={}).json()
        assert c.post("/api/telegram/digest", headers=h, json={}).json()["id"] == first["id"]
        assert "998901234567" not in first["text"] and "Buyurtmalar / Заказы: 1" in first["text"]
        calls = []

        def failing(tok, chat, text):
            calls.append(tok)
            raise RuntimeError(f"network down for bot{tok}")

        with SessionLocal() as db:
            cid = db.get(OutboxMessage, first["id"]).company_id
            assert integrations.dispatch(db, cid, failing) == {"sent": 0, "failed": 1}
            msg = db.get(OutboxMessage, first["id"])
            assert msg.status == "pending" and msg.attempts == 1 and token not in msg.last_error
            assert integrations.dispatch(db, cid, failing) == {"sent": 0, "failed": 0}  # backoff not due
            for _ in range(4):
                db.get(OutboxMessage, first["id"]).next_attempt_at = 0
                db.commit()
                integrations.dispatch(db, cid, failing)
            assert db.get(OutboxMessage, first["id"]).status == "failed" and calls[0] == token
            second = integrations.enqueue_digest(db, cid, "2026-01-01")
            db.commit()
            sent = []
            assert integrations.dispatch(db, cid, lambda t, ch, tx: sent.append(ch)) == {"sent": 1, "failed": 0}
            assert sent == ["-100123"] and db.get(OutboxMessage, second.id).status == "sent"
        assert token not in str(c.get("/api/telegram/outbox", headers=h).json())
