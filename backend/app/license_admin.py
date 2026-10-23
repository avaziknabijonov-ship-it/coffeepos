"""Server-side subscription management. Run inside the API container.

Examples:
  python -m app.license_admin list
  python -m app.license_admin grant testcoffee monthly 30
  python -m app.license_admin grant testcoffee yearly 365
  python -m app.license_admin suspend testcoffee
"""
import argparse
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from .db import Base, Company, Subscription, SessionLocal, engine, now_ms

def main() -> None:
    parser = argparse.ArgumentParser(description="CoffeePOS subscription management")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    create = sub.add_parser("create")
    create.add_argument("slug")
    create.add_argument("name")
    create.add_argument("owner_name")

    grant = sub.add_parser("grant")
    grant.add_argument("slug")
    grant.add_argument("plan", choices=["monthly", "yearly"])
    grant.add_argument("days", type=int)
    renew = sub.add_parser("renew")
    renew.add_argument("slug")
    renew.add_argument("plan", choices=["monthly", "yearly"])
    renew.add_argument("days", type=int)
    suspend = sub.add_parser("suspend")
    suspend.add_argument("slug")
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if args.action == "create":
            import re
            from .main import create_company
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}", args.slug):
                parser.error("Invalid slug")
            from getpass import getpass
            pin = getpass("Owner PIN (4-6 digits): ")
            if not re.fullmatch(r"\d{4,6}", pin):
                parser.error("PIN must contain 4-6 digits")
            if db.scalar(select(Company).where(Company.slug == args.slug)):
                parser.error("Company already exists")
            create_company(db, args.slug, args.name, args.owner_name, pin)
            db.commit()
            print("Created:", args.slug)
            return
        if args.action == "list":
            companies = db.scalars(select(Company).order_by(Company.id)).all()
            for c in companies:
                p = db.get(Subscription, c.id)
                expiry = datetime.fromtimestamp(p.expires_at / 1000, tz=timezone.utc).isoformat() if p else "none"
                print(f"{c.slug} | {p.plan if p else 'none'} | {p.status if p else 'none'} | {expiry}")
            return
        company = db.scalar(select(Company).where(Company.slug == args.slug))
        if not company:
            parser.error("Company not found")
        p = db.get(Subscription, company.id)
        if args.action in ("grant", "renew"):
            if not 1 <= args.days <= 730:
                parser.error("days must be between 1 and 730")
            current = now_ms()
            start = max(current, p.expires_at) if args.action == "renew" and p is not None and p.status == "active" else current
            expiry = start + args.days * 86400000
            if p is None:
                p = Subscription(company_id=company.id, plan=args.plan, expires_at=expiry)
                db.add(p)
            else:
                p.plan, p.status, p.expires_at, p.updated_at = args.plan, "active", expiry, now_ms()
        elif args.action == "suspend":
            if p is None:
                parser.error("Subscription not found")
            p.status, p.updated_at = "suspended", now_ms()
        db.commit()
        print(f"{args.action}: {company.slug}")

if __name__ == "__main__":
    main()
