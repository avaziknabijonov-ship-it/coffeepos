"""License expiry, renewals, and cross-tenant protection.

Use an independent in-memory SQLite test database; never touch the live DB.
"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, Subscription
from app.licensing import add_calendar_period
from app.main import app, get_db as tenant_get_db
from app.platform import get_db as platform_get_db


def test_license_expiry_blocks_mutations_but_keeps_read_access(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def db_override():
        with factory() as db:
            yield db

    monkeypatch.setenv("PLATFORM_ADMIN_KEY", "z" * 40)
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "1")
    app.dependency_overrides[tenant_get_db] = db_override
    app.dependency_overrides[platform_get_db] = db_override
    platform_headers = {"X-Platform-Key": "z" * 40}

    def register(client, slug, pin):
        r = client.post("/api/auth/register", json={
            "companyName": slug + " Cafe", "slug": slug,
            "ownerName": "Owner", "ownerPin": pin,
        })
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["token"]}

    try:
        with TestClient(app) as client:
            first = register(client, "license-a", "1234")
            second = register(client, "license-b", "2345")
            assert client.get("/api/license/status", headers=first).json()["status"] == "trial"
            assert client.get("/api/license/status", headers=second).json()["canWrite"] is True
            companies = client.get("/api/platform/companies", headers=platform_headers).json()
            a_id = next(row["id"] for row in companies if row["slug"] == "license-a")
            b_id = next(row["id"] for row in companies if row["slug"] == "license-b")

            assert client.post("/api/shifts/open", headers=first, json={"openingCash": 100_000}).status_code == 200
            with factory() as db:
                sub = db.scalar(select(Subscription).where(Subscription.company_id == a_id))
                sub.trial_ends_at = 1
                db.commit()

            expired = client.get("/api/license/status", headers=first).json()
            assert expired["status"] == "expired"
            assert expired["canWrite"] is False
            assert client.get("/api/sync", headers=first).status_code == 200
            assert client.get("/api/shifts/current", headers=first).status_code == 200
            assert client.post("/api/orders", headers=first, json={}).status_code == 403
            assert client.post("/api/expenses", headers=first, json={}).status_code == 403
            assert client.post("/api/stock", headers=first, json={}).status_code == 403
            assert client.post("/api/shifts/close", headers=first, json={}).status_code == 403

            # A different cafe must remain fully operational.
            assert client.post("/api/shifts/open", headers=second, json={"openingCash": 1_000}).status_code == 200
            assert client.get("/api/license/status", headers=second).json()["status"] == "trial"

            assert client.post(f"/api/platform/companies/{a_id}/subscription/extend", json={"days": 30}).status_code == 401
            renewed = client.post(
                f"/api/platform/companies/{a_id}/subscription/extend",
                headers=platform_headers, json={"days": 30},
            )
            assert renewed.status_code == 200, renewed.text
            assert renewed.json()["subscription"]["status"] == "active"
            assert client.get("/api/license/status", headers=first).json()["canWrite"] is True
            order = client.post("/api/orders", headers=first, json={
                "items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}],
                "customer": "Guest", "payment": "naqd", "cashGiven": 100_000,
            })
            assert order.status_code == 200, order.text

            before = renewed.json()["subscription"]["currentPeriodEndsAt"]
            extended = client.post(
                f"/api/platform/companies/{a_id}/subscription/extend",
                headers=platform_headers, json={"days": 30},
            )
            assert extended.status_code == 200, extended.text
            assert extended.json()["subscription"]["currentPeriodEndsAt"] == before + 30 * 86_400_000

            url = f"/api/platform/companies/{a_id}/subscription/extend"
            for invalid in ({}, {"period": "weekly"}, {"days": 30, "period": "monthly"}):
                bad = client.post(url, headers=platform_headers, json=invalid)
                assert bad.status_code == 422, bad.text
            paid_base = extended.json()["subscription"]["currentPeriodEndsAt"]
            monthly = client.post(url, headers=platform_headers, json={"period": "monthly"})
            assert monthly.status_code == 200, monthly.text
            month_end = monthly.json()["subscription"]["currentPeriodEndsAt"]
            assert monthly.json()["subscription"]["plan"] == "monthly"
            assert month_end == add_calendar_period(paid_base, "monthly")
            assert client.get("/api/license/status", headers=first).json()["plan"] == "monthly"
            yearly = client.post(url, headers=platform_headers, json={"period": "yearly"})
            assert yearly.status_code == 200, yearly.text
            assert yearly.json()["subscription"]["plan"] == "yearly"
            assert yearly.json()["subscription"]["currentPeriodEndsAt"] == add_calendar_period(month_end, "yearly")
            assert client.get("/api/license/status", headers=first).json()["plan"] == "yearly"

            assert client.put(f"/api/platform/companies/{a_id}/subscription",
                headers=platform_headers, json={"status": "grace"}).status_code == 422
            assert client.put(f"/api/platform/companies/{a_id}/subscription",
                headers=platform_headers, json={"status": "suspended"}).status_code == 200
            assert client.get("/api/license/status", headers=first).json()["status"] == "suspended"
            assert client.get("/api/sync", headers=first).status_code == 200
            assert client.post("/api/orders", headers=first, json={}).status_code == 403

            history = client.get(f"/api/platform/companies/{a_id}/license-history", headers=platform_headers)
            assert history.status_code == 200
            assert history.json()[0]["newStatus"] == "suspended"
            assert any(event["action"] == "extend" for event in history.json())
            assert any(event["action"] == "extend_monthly" for event in history.json())
            assert any(event["action"] == "extend_yearly" for event in history.json())
            assert client.get(f"/api/platform/companies/{b_id}/license-history", headers=platform_headers).status_code == 200
            assert client.get(f"/api/platform/companies/{b_id}/license-history").status_code == 401
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_license_grace_status_and_platform_company_pin(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[tenant_get_db] = db_override
    app.dependency_overrides[platform_get_db] = db_override
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", "y" * 40)
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "0")
    headers = {"X-Platform-Key": "y" * 40}
    create_body = {"slug": "lic-grace", "name": "Grace Coffee", "ownerName": "Rahbar", "ownerPin": "1234"}
    try:
        with TestClient(app) as client:
            # Hosted mode rejects anonymous self-registration, but platform provisioning works.
            assert client.post("/api/auth/register", json={
                "companyName": "Not Allowed", "slug": "no-self-signup",
                "ownerName": "Owner", "ownerPin": "1234",
            }).status_code == 403
            created = client.post("/api/platform/companies", json=create_body, headers=headers)
            assert created.status_code == 201, created.text
            cid = created.json()["id"]
            assert client.post("/api/auth/login", json={"company": "lic-grace", "pin": "1234"}).status_code == 200
            bad_pin = client.post("/api/platform/companies", json={
                **create_body, "slug": "too-long-pin", "ownerPin": "1234567890",
            }, headers=headers)
            assert bad_pin.status_code == 422

            now = 4102444800000
            active = client.put(f"/api/platform/companies/{cid}/subscription", headers=headers, json={
                "status": "active", "currentPeriodEndsAt": now,
                "graceEndsAt": now + 7 * 86_400_000,
            })
            assert active.status_code == 200, active.text
            with factory() as db:
                sub = db.scalar(select(Subscription).where(Subscription.company_id == cid))
                sub.current_period_ends_at = 1
                db.commit()
            auth = client.post("/api/auth/login", json={"company": "lic-grace", "pin": "1234"}).json()
            token = {"Authorization": "Bearer " + auth["token"]}
            assert client.get("/api/license/status", headers=token).json()["status"] == "grace"
            assert client.post("/api/shifts/open", headers=token, json={"openingCash": 100}).status_code == 200
            with factory() as db:
                sub = db.scalar(select(Subscription).where(Subscription.company_id == cid))
                sub.grace_ends_at = 1
                db.commit()
            assert client.get("/api/license/status", headers=token).json()["status"] == "expired"
            assert client.post("/api/shifts/close", headers=token, json={}).status_code == 403
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
