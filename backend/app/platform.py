"""Platform-only subscription administration.

Temporary bootstrap authentication: a long random PLATFORM_ADMIN_KEY environment
secret, distinct from all tenant PINs/tokens. Replace with dedicated admin identities
and MFA before production.
"""
import os
import secrets
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Company, LicenseAudit, Subscription, now_ms
from .security import hash_pin

router = APIRouter(prefix="/api/platform", tags=["platform"])
page_router = APIRouter()


@page_router.get("/platform-admin", response_class=HTMLResponse, include_in_schema=False)
def platform_admin_page() -> HTMLResponse:
    page = Path(__file__).with_name("platform_admin.html")
    return HTMLResponse(page.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'", "X-Content-Type-Options": "nosniff"})



def platform_auth(x_platform_key: str = Header(default="")) -> None:
    configured = os.environ.get("PLATFORM_ADMIN_KEY", "")
    if len(configured) < 32 or not x_platform_key or not secrets.compare_digest(configured, x_platform_key):
        raise HTTPException(401, "Platform administrator access required")


def get_db():
    from .db import SessionLocal
    with SessionLocal() as db:
        yield db


@router.get("/companies", dependencies=[Depends(platform_auth)])
def companies(db: Session = Depends(get_db)) -> list[dict]:
    result = []
    for company in db.scalars(select(Company).order_by(Company.id)).all():
        sub = db.scalar(select(Subscription).where(Subscription.company_id == company.id))
        result.append({
            "id": company.id, "slug": company.slug, "name": company.name,
            "subscription": subscription_out(sub),
        })
    return result


def subscription_out(sub: Subscription | None) -> dict | None:
    if sub is None:
        return None
    return {
        "status": sub.status, "trialEndsAt": sub.trial_ends_at,
        "currentPeriodEndsAt": sub.current_period_ends_at,
        "graceEndsAt": sub.grace_ends_at, "updatedAt": sub.updated_at,
    }


class SubscriptionUpdate(BaseModel):
    status: Literal["trial", "active", "grace", "expired", "suspended"]
    trialEndsAt: int | None = None
    currentPeriodEndsAt: int | None = None
    graceEndsAt: int | None = None


@router.put("/companies/{company_id}/subscription", dependencies=[Depends(platform_auth)])
def update_subscription(company_id: int, body: SubscriptionUpdate, db: Session = Depends(get_db)) -> dict:
    if db.get(Company, company_id) is None:
        raise HTTPException(404, "Coffee bar not found")
    if body.status == "trial" and (body.trialEndsAt is None or body.trialEndsAt <= now_ms()):
        raise HTTPException(422, "Trial needs a future trialEndsAt")
    if body.status == "active" and (body.currentPeriodEndsAt is None or body.currentPeriodEndsAt <= now_ms()):
        raise HTTPException(422, "Active subscription needs a future currentPeriodEndsAt")
    sub = db.scalar(select(Subscription).where(Subscription.company_id == company_id))
    previous = sub.status if sub else None
    if sub is None:
        sub = Subscription(company_id=company_id)
        db.add(sub)
    sub.status = body.status
    sub.trial_ends_at = body.trialEndsAt
    sub.current_period_ends_at = body.currentPeriodEndsAt
    sub.grace_ends_at = body.graceEndsAt
    sub.updated_at = now_ms()
    db.add(LicenseAudit(company_id=company_id, action="manual_update", old_status=previous, new_status=body.status))
    db.commit()
    return {"companyId": company_id, "subscription": subscription_out(sub)}


class CompanyCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=40, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=128)
    ownerName: str = Field(min_length=2, max_length=64)
    ownerPin: str = Field(min_length=6, max_length=12, pattern=r"^[0-9]+$")


@router.post("/companies", status_code=201, dependencies=[Depends(platform_auth)])
def create_platform_company(body: CompanyCreate, db: Session = Depends(get_db)) -> dict:
    """Create a new isolated tenant with the standard starter menu and 14-day trial."""
    if db.scalar(select(Company).where(Company.slug == body.slug)):
        raise HTTPException(409, "Coffee bar login already exists")
    # Import here to avoid a circular import: main mounts the platform router.
    from .main import create_company
    try:
        company = create_company(db, body.slug, body.name.strip(), body.ownerName.strip(), body.ownerPin)
        db.flush()
        db.add(LicenseAudit(company_id=company.id, action="company_created", old_status=None, new_status="trial"))
        db.commit()
        return {"id": company.id, "slug": company.slug, "name": company.name, "status": "trial"}
    except Exception:
        db.rollback()
        raise
