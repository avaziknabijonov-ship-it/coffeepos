"""G0: branch isolation, staff binding and versioned migrations."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import migrations
from helpers import LATTE, at, new_company, staff_login
from test_api import app


def test_branch_scoped_shift_orders_stock_and_cash():
    with TestClient(app) as c:
        owner, slug = new_company(c, "br")
        branches = c.get("/api/branches", headers=owner).json()
        main_id = branches["current"]
        assert [b["isDefault"] for b in branches["items"]] == [True]
        second = c.post("/api/branches", json={"name": "Chilonzor"}, headers=owner)
        assert second.status_code == 201
        sid = second.json()["id"]
        assert c.post("/api/branches", json={"name": "Chilonzor"}, headers=owner).status_code == 409

        assert c.post("/api/shifts/open", json={"openingCash": 1000}, headers=owner).status_code == 200
        assert c.post("/api/orders", json=LATTE, headers=at(owner, sid)).status_code == 409
        assert c.post("/api/shifts/open", json={"openingCash": 5000}, headers=at(owner, sid)).status_code == 200
        r = c.post("/api/orders", json=LATTE, headers=at(owner, sid))
        assert r.status_code == 200, r.text
        assert r.json()["number"] == 1

        main_sync = c.get("/api/sync", headers=owner).json()
        second_sync = c.get("/api/sync", headers=at(owner, sid)).json()
        assert main_sync["orders"] == [] and len(second_sync["orders"]) == 1
        assert second_sync["stock"]["beans"] < 0 and main_sync["stock"]["beans"] == 0
        assert second_sync["shift"]["expectedCash"] == 5000 + r.json()["total"]
        assert main_sync["shift"]["expectedCash"] == 1000

        kassir, kid = staff_login(c, owner, slug, "kassir", "2468")
        assert c.put(f"/api/staff/{kid}/branch", json={"branchId": sid}, headers=owner).status_code == 200
        assert c.get("/api/me", headers=kassir).json()["branch"]["id"] == sid
        assert c.get("/api/sync", headers=at(kassir, main_id)).status_code == 403
        assert [b["id"] for b in c.get("/api/branches", headers=kassir).json()["items"]] == [sid]
        assert c.post("/api/branches", json={"name": "X"}, headers=kassir).status_code == 403
        assert c.patch(f"/api/branches/{main_id}", json={"active": False}, headers=owner).status_code == 409


def test_branch_header_cannot_cross_tenants():
    with TestClient(app) as c:
        a, _ = new_company(c, "bra")
        b, _ = new_company(c, "brb")
        foreign = c.post("/api/branches", json={"name": "B2"}, headers=b).json()["id"]
        assert c.get("/api/sync", headers=at(a, foreign)).status_code == 404
        assert c.get("/api/sync", headers=at(a, "abc")).status_code == 422
        assert c.get(f"/api/branches/{foreign}/stock", headers=a).status_code == 404


def test_versioned_migrations_upgrade_legacy_schema(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE companies (id INTEGER PRIMARY KEY, slug VARCHAR(64), name VARCHAR(128), created_at BIGINT)"))
        conn.execute(text("INSERT INTO companies VALUES (1, 'old', 'Old', 0)"))
    from app import db as dbmod
    from sqlalchemy.orm import sessionmaker
    dbmod.Base.metadata.create_all(engine)
    monkeypatch.setattr(migrations, "SessionLocal", sessionmaker(engine))
    with sessionmaker(engine)() as session:
        session.add(dbmod.Staff(id=1, company_id=1, name="Ali", role="kassir", pin_hash="x"))
        session.add(dbmod.Shift(id=1, company_id=1, staff_name="Ali", opening_cash=0))
        session.commit()
    assert migrations.run(engine) == [v for v, _, _ in migrations.MIGRATIONS]
    assert migrations.run(engine) == []
    with engine.begin() as conn:
        branch = conn.execute(text("SELECT id FROM branches WHERE company_id = 1 AND is_default")).scalar_one()
        assert conn.execute(text("SELECT branch_id, staff_id FROM shifts WHERE id = 1")).one() == (branch, 1)
