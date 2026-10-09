"""Platform authorization and subscription administration tests."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, Company, Subscription
from app.main import app
from app.platform import get_db


def test_platform_auth_and_subscription(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        company = Company(slug="pilot", name="Pilot Coffee")
        db.add(company)
        db.commit()
        cid = company.id

    def db_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", "x" * 40)
    try:
        with TestClient(app) as client:
            assert client.get("/api/platform/companies").status_code == 401
            assert client.get("/api/platform/companies", headers={"X-Platform-Key": "wrong"}).status_code == 401
            headers = {"X-Platform-Key": "x" * 40}
            result = client.get("/api/platform/companies", headers=headers)
            assert result.status_code == 200
            assert result.json()[0]["slug"] == "pilot"
            assert client.put(f"/api/platform/companies/{cid}/subscription", headers=headers, json={"status": "active"}).status_code == 422
            updated = client.put(f"/api/platform/companies/{cid}/subscription", headers=headers, json={
                "status": "active", "currentPeriodEndsAt": 4102444800000,
            })
            assert updated.status_code == 200
            with factory() as db:
                assert db.query(Subscription).filter_by(company_id=cid).one().status == "active"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
