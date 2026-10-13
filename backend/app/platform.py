"""Platform management with individual administrator attribution and least privilege."""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Company, LicenseAudit, LicenseOperation, PlatformAdmin, PlatformAudit, Setting, Subscription, now_ms
from .licensing import add_calendar_period, subscription_payload
from .platform_security import (
    BootstrapAdmin, CreateAdmin, EditAdmin, EnrollRequest, FinishEnrollment,
    PlatformActor, PlatformLogin, audit, bootstrap_admin, create_platform_session,
    ensure_last_superadmin, finish_enrollment, has_admins, new_admin,
    platform_auth, require_role, start_enrollment, _issue_invitation,
)

router = APIRouter(prefix="/api/platform", tags=["platform"])
page_router = APIRouter()


@page_router.get("/platform-admin", response_class=HTMLResponse, include_in_schema=False)
def platform_admin_page() -> HTMLResponse:
    page = Path(__file__).with_name("platform_admin.html")
    return HTMLResponse(page.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'", "X-Content-Type-Options": "nosniff"})



def get_db():
    from .db import SessionLocal
    with SessionLocal() as db:
        yield db


def auth_platform(
    db: Session = Depends(get_db),
    x_platform_session: str = Header(default=""),
    x_platform_key: str = Header(default=""),
) -> PlatformActor:
    return platform_auth(db, x_platform_session=x_platform_session, x_platform_key=x_platform_key)


def superadmin(actor: PlatformActor = Depends(auth_platform)) -> PlatformActor:
    require_role(actor, ("superadmin",))
    return actor


def can_manage(actor: PlatformActor = Depends(auth_platform)) -> PlatformActor:
    require_role(actor, ("superadmin", "manager"))
    return actor


def license_audit(
    db: Session, actor: PlatformActor, request: Request, company_id: int,
    action: str, before: dict | None, after: dict | None,
    old_status: str | None, new_status: str,
) -> None:
    snapshot = {"before": before, "after": after}
    db.add(LicenseAudit(
        company_id=company_id, action=action, old_status=old_status,
        new_status=new_status, actor_username=actor.username, details=snapshot,
    ))
    audit(db, action, actor.username, request, companyId=company_id, **snapshot)


# Pricing is optional. NULL means no approved tariff price has been set.
# Prices are informational until an actual verified billing integration exists.
PRICING_KEYS = {"monthly": "license_price_monthly_uzs", "yearly": "license_price_yearly_uzs"}


class PricingUpdate(BaseModel):
    monthly: int | None = Field(default=None, gt=0, le=10_000_000_000)
    yearly: int | None = Field(default=None, gt=0, le=10_000_000_000)


def pricing_out(db: Session) -> dict:
    settings = {
        setting.key: setting.value
        for setting in db.scalars(select(Setting).where(Setting.key.in_(list(PRICING_KEYS.values()))))
    }
    return {
        "currency": "UZS",
        **{period: int(settings[key]) if key in settings else None for period, key in PRICING_KEYS.items()},
    }


@router.post("/session")
def platform_session(body: PlatformLogin, request: Request, db: Session = Depends(get_db)) -> dict:
    return create_platform_session(body, request, db)


@router.post("/bootstrap")
def platform_bootstrap(body: BootstrapAdmin, request: Request, db: Session = Depends(get_db)) -> dict:
    return bootstrap_admin(db, body, request)


@router.post("/enroll/start")
def enroll_start(body: EnrollRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    return start_enrollment(db, body, request)


@router.post("/enroll/complete")
def enroll_complete(body: FinishEnrollment, request: Request, db: Session = Depends(get_db)) -> dict:
    return finish_enrollment(db, body, request)


@router.post("/logout")
def platform_logout(request: Request, db: Session = Depends(get_db),
                    actor: PlatformActor = Depends(auth_platform)) -> dict:
    if actor.id is not None:
        admin = db.get(PlatformAdmin, actor.id)
        admin.session_version += 1
    audit(db, "admin_logout", actor.username, request)
    db.commit()
    return {"ok": True}


@router.get("/me")
def platform_me(actor: PlatformActor = Depends(auth_platform)) -> dict:
    return {"username": actor.username, "role": actor.role, "individual": actor.id is not None}



@router.get("/pricing", dependencies=[Depends(auth_platform)])
def pricing(db: Session = Depends(get_db)) -> dict:
    return pricing_out(db)


@router.put("/pricing", dependencies=[Depends(auth_platform)])
def update_pricing(body: PricingUpdate, db: Session = Depends(get_db)) -> dict:
    before = pricing_out(db)
    changes = body.model_dump()
    for period, key in PRICING_KEYS.items():
        existing = db.get(Setting, key)
        value = changes[period]
        if value is None:
            if existing:
                db.delete(existing)
        elif existing:
            existing.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    db.add(PlatformAudit(action="pricing_update", details={"before": before, "after": {"currency": "UZS", **changes}}))
    db.commit()
    return pricing_out(db)


@router.get("/platform-history", dependencies=[Depends(auth_platform)])
def platform_history(db: Session = Depends(get_db)) -> list[dict]:
    events = db.scalars(select(PlatformAudit).order_by(PlatformAudit.id.desc()).limit(50)).all()
    return [{"action": event.action, "details": event.details, "createdAt": event.created_at} for event in events]


@router.get("/companies", dependencies=[Depends(auth_platform)])
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
        **subscription_payload(sub),
        "storedStatus": sub.status,
        "updatedAt": sub.updated_at,
    }


class SubscriptionUpdate(BaseModel):
    status: Literal["trial", "active", "grace", "expired", "suspended"]
    trialEndsAt: int | None = None
    currentPeriodEndsAt: int | None = None
    graceEndsAt: int | None = None


@router.put("/companies/{company_id}/subscription", dependencies=[Depends(auth_platform)])
def update_subscription(company_id: int, body: SubscriptionUpdate, db: Session = Depends(get_db)) -> dict:
    if db.get(Company, company_id) is None:
        raise HTTPException(404, "Coffee bar not found")
    now = now_ms()
    if body.status == "trial" and (body.trialEndsAt is None or body.trialEndsAt <= now):
        raise HTTPException(422, "Trial needs a future trialEndsAt")
    if body.status == "active" and (body.currentPeriodEndsAt is None or body.currentPeriodEndsAt <= now):
        raise HTTPException(422, "Active subscription needs a future currentPeriodEndsAt")
    if body.status == "grace" and (body.graceEndsAt is None or body.graceEndsAt <= now):
        raise HTTPException(422, "Grace needs a future graceEndsAt")
    if body.status == "active" and body.graceEndsAt is not None and body.graceEndsAt <= body.currentPeriodEndsAt:
        raise HTTPException(422, "Grace date must be after active subscription expiry")
    sub = db.scalar(select(Subscription).where(Subscription.company_id == company_id))
    previous = sub.status if sub else None
    if sub is None:
        sub = Subscription(company_id=company_id)
        db.add(sub)
    sub.status = body.status
    # Direct manual date changes do not imply a monthly or yearly plan.
    sub.plan = None
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
    ownerPin: str = Field(min_length=4, max_length=6, pattern=r"^[0-9]+$")


@router.post("/companies", status_code=201, dependencies=[Depends(auth_platform)])
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


class SubscriptionExtend(BaseModel):
    # Calendar subscription plans require an idempotency operation ID.
    # Legacy days remain supported for older integrations only.
    period: Literal["monthly", "yearly"] | None = None
    days: int | None = Field(default=None, ge=1, le=3650)
    operationId: str | None = Field(default=None, min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


@router.post("/companies/{company_id}/subscription/extend", dependencies=[Depends(auth_platform)])
def extend_subscription(company_id: int, body: SubscriptionExtend, db: Session = Depends(get_db)) -> dict:
    """Manual extension. This is NOT payment processing or receipt verification."""
    # Serialize grants per cafe on PostgreSQL; the unique operation ID is an
    # additional DB-level safeguard for simultaneous/retried requests.
    company = db.scalar(select(Company).where(Company.id == company_id).with_for_update())
    if company is None:
        raise HTTPException(404, "Coffee bar not found")
    if (body.period is None) == (body.days is None):
        raise HTTPException(422, "Specify exactly one of period or days")
    if body.period is not None and not body.operationId:
        raise HTTPException(422, "A unique operationId is required for monthly/yearly grants")
    sub = db.scalar(select(Subscription).where(Subscription.company_id == company_id))
    if body.operationId:
        prior = db.scalar(select(LicenseOperation).where(
            LicenseOperation.company_id == company_id,
            LicenseOperation.operation_id == body.operationId,
        ))
        if prior:
            requested_period = body.period if body.period else f"days:{body.days}"
            if prior.period != requested_period:
                raise HTTPException(409, "This operationId was already used for a different grant")
            # Idempotent retries return the original grant date, not a new period.
            return {
                "companyId": company_id, "replayed": True,
                "grantedUntil": prior.new_end_at,
                "subscription": subscription_out(sub),
            }
    previous = sub.status if sub else None
    if sub is None:
        sub = Subscription(company_id=company_id)
        db.add(sub)
    now = now_ms()
    # Preserve the remaining paid period; an expired or trial account starts today.
    base = max(now, sub.current_period_ends_at or 0) if sub.status == "active" else now
    sub.status = "active"
    sub.plan = body.period  # Legacy day-based records remain without a named plan.
    sub.current_period_ends_at = (
        add_calendar_period(base, body.period)
        if body.period is not None
        else base + body.days * 86_400_000
    )
    sub.grace_ends_at = None
    sub.updated_at = now
    if body.operationId:
        db.add(LicenseOperation(
            company_id=company_id,
            operation_id=body.operationId,
            period=body.period if body.period else f"days:{body.days}",
            previous_end_at=base,
            new_end_at=sub.current_period_ends_at,
        ))
    db.add(LicenseAudit(
        company_id=company_id,
        action="extend_monthly" if body.period == "monthly"
               else "extend_yearly" if body.period == "yearly" else "extend",
        old_status=previous, new_status="active",
    ))
    db.commit()
    return {"companyId": company_id, "replayed": False, "grantedUntil": sub.current_period_ends_at, "subscription": subscription_out(sub)}


@router.get("/companies/{company_id}/license-history", dependencies=[Depends(auth_platform)])
def license_history(company_id: int, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(Company, company_id) is None:
        raise HTTPException(404, "Coffee bar not found")
    events = db.scalars(select(LicenseAudit).where(
        LicenseAudit.company_id == company_id
    ).order_by(LicenseAudit.id.desc()).limit(100)).all()
    return [{
        "id": event.id,
        "action": event.action,
        "oldStatus": event.old_status,
        "newStatus": event.new_status,
        "createdAt": event.created_at,
    } for event in events]
