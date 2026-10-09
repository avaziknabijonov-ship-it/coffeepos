"""Basic subscription model tests; run with pytest from backend directory."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base, Company, Subscription


def test_subscription_persists_for_tenant():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        company = Company(slug="trial-test", name="Trial Test")
        db.add(company)
        db.flush()
        db.add(Subscription(company_id=company.id, status="trial", trial_ends_at=1_800_000_000_000))
        db.commit()
        found = db.scalar(select(Subscription).where(Subscription.company_id == company.id))
        assert found is not None
        assert found.status == "trial"
        assert found.trial_ends_at == 1_800_000_000_000
