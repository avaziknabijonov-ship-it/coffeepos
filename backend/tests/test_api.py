import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def login(c, pin, company="demo"):
    r = c.post("/api/auth/login", json={"company": company, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_full_flow():
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"company": "demo", "pin": "9999"}).status_code == 401
        owner, kassir, barista = login(c, "1111"), login(c, "2222"), login(c, "3333")

        menu = c.get("/api/menu", headers=kassir).json()
        assert len(menu["products"]) == 17
        beans_before = next(i for i in menu["ingredients"] if i["id"] == "beans")["stock"]
        almond_before = next(i for i in menu["ingredients"] if i["id"] == "almond")["stock"]

        order = {"items": [{"productId": "latte", "size": "M", "modIds": ["milk-almond", "shot1"], "qty": 2}],
                 "customer": "Aziz", "payment": "naqd", "cashGiven": 100000}
        assert c.post("/api/orders", json=order, headers=kassir).status_code == 409
        assert c.post("/api/shifts/open", json={"openingCash": 200000}, headers=barista).status_code == 403
        assert c.post("/api/shifts/open", json={"openingCash": 200000}, headers=kassir).status_code == 200

        r = c.post("/api/orders", json=order, headers=kassir)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["number"] == 1 and o["total"] == 2 * (30000 + 6000 + 5000)
        assert c.post("/api/orders", json={**order, "discountPct": 51}, headers=kassir).status_code == 403
        assert c.post("/api/orders", json={**order, "discountPct": 50}, headers=kassir).status_code == 200
        assert c.post("/api/orders", json={**order, "discountPct": 15}, headers=kassir).status_code == 200

        assert o["items"][0]["mods"] == ["Bodom suti", "+1 shot"]

        stock = c.get("/api/sync", headers=barista).json()["stock"]
        assert stock["beans"] == beans_before - 2 * (18 + 9)
        assert stock["almond"] == almond_before - 2 * 240

        bad = {**order, "items": [{"productId": "espresso", "size": "-", "modIds": ["milk-almond"]}]}
        assert c.post("/api/orders", json=bad, headers=kassir).status_code == 400

        assert c.patch(f"/api/orders/{o['id']}", json={"status": "ready"}, headers=barista).json()["readyAt"]

        assert c.patch("/api/products/latte/active", json={"active": False}, headers=kassir).status_code == 200
        assert c.post("/api/orders", json=order, headers=kassir).status_code == 400

        assert c.get("/api/staff", headers=kassir).status_code == 403
        assert c.post("/api/staff", json={"name": "X", "role": "barista", "pin": "2222"}, headers=owner).status_code == 409
        assert c.post("/api/staff", json={"name": "Lola", "role": "barista", "pin": "4444"}, headers=owner).status_code == 200
        login(c, "4444")

        r = c.post("/api/stock", json={"ing": "beans", "qty": 1000, "reason": "intake"}, headers=owner)
        assert r.json()["stock"] == stock["beans"] + 1000

        closed = c.post("/api/shifts/close", json={"closingCash": 282000, "closingPayments": {"karta": 0, "payme": 0, "click": 0}}, headers=kassir).json()
        assert closed["expectedCash"] == 200000 + 82000 and closed["difference"] == 0
        assert c.get("/api/reports/daily", headers=owner).json()[-1]["revenue"] == 82000


def test_register_is_isolated():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"companyName": "Bek Kofe", "slug": "bek-kofe", "ownerName": "Bek", "ownerPin": "1111"})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert r.json()["staff"]["role"] == "owner"
        assert c.get("/api/sync", headers=h).json()["orders"] == []
        assert c.post("/api/auth/register", json={"companyName": "Boshqa", "slug": "bek-kofe", "ownerName": "Vali", "ownerPin": "2222"}).status_code == 409


def test_inventory_and_losses():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"companyName": "Inv Kofe", "slug": "inv-kofe", "ownerName": "Ali", "ownerPin": "1111"})
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        ings = {i["id"]: i for i in c.get("/api/menu", headers=h).json()["ingredients"]}
        beans, milk = ings["beans"], ings["milk"]

        assert c.post("/api/stock", json={"ing": "beans", "qty": 100, "reason": "writeoff", "note": "bad"}, headers=h).status_code == 422
        r = c.post("/api/stock", json={"ing": "beans", "qty": 100, "reason": "writeoff", "note": "spill"}, headers=h)
        assert r.json()["stock"] == beans["stock"] - 100

        lines = [{"ing": "beans", "counted": beans["stock"] - 150}, {"ing": "milk", "counted": milk["stock"] + 200}]
        assert c.post("/api/inventories", json={"lines": lines + lines[:1]}, headers=h).status_code == 400
        inv = c.post("/api/inventories", json={"lines": lines, "note": "Oy oxiri"}, headers=h).json()
        assert inv["lines"][0]["expected"] == beans["stock"] - 100 and inv["lines"][0]["diff"] == -50
        assert inv["shortage"] == round(50 * beans["cost"]) and inv["surplus"] == round(200 * milk["cost"])
        stock = c.get("/api/sync", headers=h).json()["stock"]
        assert stock["beans"] == beans["stock"] - 150 and stock["milk"] == milk["stock"] + 200
        assert [x["id"] for x in c.get("/api/inventories", headers=h).json()] == [inv["id"]]

        rep = c.get("/api/reports/losses?days=30", headers=h).json()
        assert rep["byNote"] == {"spill": round(100 * beans["cost"])}
        assert rep["inventories"] == 1 and rep["shortage"] == inv["shortage"]
        assert rep["items"][0]["ing"] == "beans" and rep["items"][0]["writeoffQty"] == 100


def test_shift_expenses_profit_and_historical_report():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={"companyName": "Report Cafe", "slug": "report-cafe", "ownerName": "Manager", "ownerPin": "1234"})
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert c.post("/api/shifts/open", json={"openingCash": 100000}, headers=h).status_code == 200
        e = c.post("/api/expenses", json={"amount": 5000, "category": "Transport", "method": "payme", "note": "Taxi"}, headers=h)
        assert e.status_code == 200, e.text
        current = c.get("/api/shifts/current", headers=h).json()
        assert current["expectedPayments"]["payme"] == -5000
        assert current["expensesByMethod"]["payme"] == 5000
        assert c.post("/api/shifts/close", json={"closingCash": 100000}, headers=h).status_code == 422
        closed = c.post("/api/shifts/close", json={"closingCash": 100000, "closingPayments": {"karta": 0, "payme": 0, "click": 0}}, headers=h)
        assert closed.status_code == 200, closed.text
        shift_id = closed.json()["shift"]["id"]
        history = c.get(f"/api/shifts/{shift_id}/report", headers=h)
        assert history.status_code == 200, history.text
        assert history.json()["expenseDetails"][0]["note"] == "Taxi"
        assert history.json()["shift"]["closingPayments"]["payme"] == 0
        profit = c.get("/api/reports/profit?period=day", headers=h)
        assert profit.status_code == 200, profit.text
        assert profit.json()["expenses"] == 5000
        assert profit.json()["netProfit"] == -5000


def test_cash_expense_cannot_exceed_shift_balance():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={
            "companyName": "Cash Guard Cafe", "slug": "cash-guard-cafe",
            "ownerName": "Owner", "ownerPin": "1234",
        })
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        assert c.post("/api/shifts/open", json={"openingCash": 28000}, headers=h).status_code == 200
        too_much = c.post("/api/expenses", json={
            "amount": 50000, "category": "Transport", "method": "naqd",
        }, headers=h)
        assert too_much.status_code == 409, too_much.text
        assert c.get("/api/expenses", headers=h).json() == []
        ok = c.post("/api/expenses", json={
            "amount": 20000, "category": "Transport", "method": "naqd",
        }, headers=h)
        assert ok.status_code == 200, ok.text
        current = c.get("/api/shifts/current", headers=h).json()
        assert current["expectedCash"] == 8000
        assert c.post("/api/expenses", json={
            "amount": 8001, "category": "Transport", "method": "naqd",
        }, headers=h).status_code == 409
        assert len(c.get("/api/expenses", headers=h).json()) == 1


def test_daily_salary_carries_unpaid_balance_into_next_month():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={
            "companyName": "Wage Carry Cafe", "slug": "wage-carry-cafe",
            "ownerName": "Owner", "ownerPin": "1234",
        })
        assert r.status_code == 200, r.text
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        staff = c.get("/api/staff", headers=h).json()
        sid = next(s["id"] for s in staff if s["role"] == "owner")
        assert c.patch(f"/api/staff/{sid}/salary", json={
            "salaryType": "daily", "salaryRate": 100000,
        }, headers=h).status_code == 200
        for _ in range(2):
            assert c.post("/api/salary/entries", json={
                "staffId": sid, "kind": "day", "amount": 1,
            }, headers=h).status_code == 200
        assert c.post("/api/salary/entries", json={
            "staffId": sid, "kind": "payment", "amount": 50000,
        }, headers=h).status_code == 200
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Tashkent"))
        month = f"{now.year}-{now.month:02d}"
        current = c.get(f"/api/salary?month={month}", headers=h).json()
        row = next(s for s in current if s["staffId"] == sid)
        assert row["earned"] == 200000
        assert row["remaining"] == 150000
        future_month = f"{now.year + (now.month == 12)}-{(now.month % 12) + 1:02d}"
        future = c.get(f"/api/salary?month={future_month}", headers=h).json()
        future_row = next(s for s in future if s["staffId"] == sid)
        assert future_row["remaining"] == 150000


def test_daily_rate_change_preserves_old_accrual():
    with TestClient(app) as client:
        result = client.post("/api/auth/register", json={"companyName": "Rate History", "slug": "rate-history", "ownerName": "Owner", "ownerPin": "1234"})
        auth = {"Authorization": f"Bearer {result.json()['token']}"}
        sid = client.get("/api/staff", headers=auth).json()[0]["id"]
        def rate(value):
            return client.patch(f"/api/staff/{sid}/salary", json={"salaryType": "daily", "salaryRate": value}, headers=auth)
        def entry(kind, amount):
            return client.post("/api/salary/entries", json={"staffId": sid, "kind": kind, "amount": amount}, headers=auth)
        assert rate(100000).status_code == 200
        assert entry("day", 2).status_code == 200
        assert rate(150000).status_code == 200
        assert entry("day", 1).status_code == 200
        assert entry("payment", 50000).status_code == 200
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Tashkent"))
        report = client.get(f"/api/salary?month={now.year}-{now.month:02d}", headers=auth).json()
        record = next(item for item in report if item["staffId"] == sid)
        assert record["earned"] == 350000
        assert record["remaining"] == 300000
