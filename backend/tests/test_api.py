import os
import tempfile

os.environ["ALLOW_PUBLIC_REGISTRATION"] = "1"
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
        assert o["items"][0]["mods"] == ["Bodom suti", "+1 shot"]

        stock = c.get("/api/sync", headers=barista).json()["stock"]
        assert stock["beans"] == beans_before - 2 * (18 + 9)
        assert stock["almond"] == almond_before - 2 * 240

        bad = {**order, "items": [{"productId": "espresso", "size": "-", "modIds": ["milk-almond"]}]}
        assert c.post("/api/orders", json=bad, headers=kassir).status_code == 400

        assert c.post("/api/orders", json=order, headers=barista).status_code == 403
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "preparing"}, headers=kassir).status_code == 403
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "ready"}, headers=barista).status_code == 409
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "preparing"}, headers=barista).status_code == 200
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "ready"}, headers=barista).json()["readyAt"]
        assert c.patch(f"/api/orders/{o['id']}", json={"status": "done"}, headers=barista).status_code == 200

        assert c.patch("/api/products/latte/active", json={"active": False}, headers=kassir).status_code == 200
        assert c.post("/api/orders", json=order, headers=kassir).status_code == 400

        assert c.get("/api/staff", headers=kassir).status_code == 403
        assert c.post("/api/staff", json={"name": "X", "role": "barista", "pin": "2222"}, headers=owner).status_code == 409
        assert c.post("/api/staff", json={"name": "Lola", "role": "barista", "pin": "4444"}, headers=owner).status_code == 200
        login(c, "4444")

        invoice = {
            "number": "TEST-001", "supplier": "Test Supplier", "received_at": 1780000000000,
            "payment_status": "paid", "lines": [{"ing": "beans", "qty": 1000, "unit_price": 100}],
        }
        response = c.post("/api/purchases", json=invoice, headers=owner)
        assert response.status_code == 200, response.text
        assert c.get("/api/sync", headers=owner).json()["stock"]["beans"] == stock["beans"] + 1000

        closed = c.post("/api/shifts/close", json={"closingCash": 282000}, headers=kassir).json()
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


def test_expense_isolation_and_permissions():
    with TestClient(app) as c:
        a = c.post("/api/auth/register", json={"companyName": "Coffee A", "slug": "company-a", "ownerName": "A", "ownerPin": "4567"})
        b = c.post("/api/auth/register", json={"companyName": "Coffee B", "slug": "company-b", "ownerName": "B", "ownerPin": "5678"})
        assert a.status_code == 200 and b.status_code == 200
        ah = {"Authorization": "Bearer " + a.json()["token"]}
        bh = {"Authorization": "Bearer " + b.json()["token"]}
        created = c.post("/api/expenses", json={"amount": 10000, "category": "Transport", "payment": "cash"}, headers=ah)
        assert created.status_code == 200, created.text
        assert len(c.get("/api/expenses", headers=ah).json()) == 1
        assert c.get("/api/expenses", headers=bh).json() == []
        assert c.post("/api/expenses", json={"amount": -1, "category": "Bad"}, headers=ah).status_code == 422


def test_combined_cashier_barista_permission():
    with TestClient(app) as c:
        registered = c.post("/api/auth/register", json={
            "companyName": "Dual Role Cafe", "slug": "dual-role-cafe",
            "ownerName": "Owner", "ownerPin": "8751"
        })
        assert registered.status_code == 200, registered.text
        owner = {"Authorization": "Bearer " + registered.json()["token"]}
        assert c.post("/api/staff", headers=owner, json={
            "name": "Combined", "role": "kassir", "pin": "8752", "canBarista": True
        }).json()["canBarista"] is True
        assert c.post("/api/staff", headers=owner, json={
            "name": "OnlyCashier", "role": "kassir", "pin": "8753"
        }).json()["canBarista"] is False
        assert c.post("/api/staff", headers=owner, json={
            "name": "OnlyBarista", "role": "barista", "pin": "8754"
        }).status_code == 200
        combo, regular, barista = (
            login(c, "8752", "dual-role-cafe"),
            login(c, "8753", "dual-role-cafe"),
            login(c, "8754", "dual-role-cafe"),
        )
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=combo).status_code == 200
        order = c.post("/api/orders", headers=combo, json={
            "items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}],
            "payment": "naqd", "cashGiven": 100000
        })
        assert order.status_code == 200, order.text
        url = "/api/orders/" + order.json()["id"]
        assert c.patch(url, headers=regular, json={"status": "preparing"}).status_code == 403
        assert c.patch(url, headers=combo, json={"status": "preparing"}).status_code == 200
        staff = c.get("/api/staff", headers=owner).json()
        combined = next(x for x in staff if x["name"] == "Combined")
        updated = c.put("/api/staff/" + str(combined["id"]), headers=owner, json={
            "name": combined["name"], "role": "kassir", "active": True, "canBarista": False
        })
        assert updated.status_code == 200 and updated.json()["canBarista"] is False
        assert c.patch(url, headers=combo, json={"status": "ready"}).status_code == 403
        assert c.patch(url, headers=barista, json={"status": "ready"}).status_code == 200
        assert c.post("/api/orders", headers=barista, json={
            "items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}],
            "payment": "naqd", "cashGiven": 100000
        }).status_code == 403


def test_idempotent_sales_and_cashier_cash_spending():
    with TestClient(app) as c:
        created = c.post("/api/auth/register", json={
            "companyName": "Safe Retry Coffee", "slug": "safe-retry-coffee",
            "ownerName": "Owner", "ownerPin": "7381"
        })
        assert created.status_code == 200, created.text
        owner = {"Authorization": "Bearer " + created.json()["token"]}
        added = c.post("/api/staff", json={
            "name": "Cashier", "role": "kassir", "pin": "7382"
        }, headers=owner)
        assert added.status_code == 200, added.text
        cashier = login(c, "7382", "safe-retry-coffee")
        assert c.post("/api/expenses", headers=cashier, json={
            "amount": 500, "category": "Boshqa", "payment": "cash"
        }).status_code == 409
        assert c.post("/api/shifts/open", headers=cashier, json={
            "openingCash": 10000
        }).status_code == 200
        first_expense = c.post("/api/expenses", headers=cashier, json={
            "amount": 5000, "category": "Transport", "payment": "cash"
        })
        assert first_expense.status_code == 200, first_expense.text
        assert c.get("/api/sync", headers=cashier).json()["shift"]["expectedCash"] == 5000
        assert c.post("/api/expenses", headers=cashier, json={
            "amount": 2000, "category": "Transport", "payment": "card"
        }).status_code == 200
        assert c.get("/api/sync", headers=cashier).json()["shift"]["expectedCash"] == 5000
        stock0 = c.get("/api/sync", headers=cashier).json()["stock"]["beans"]
        payload = {
            "clientKey": "offline-retry-tx-00001",
            "items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}],
            "payment": "naqd", "cashGiven": 50000
        }
        created_order = c.post("/api/orders", headers=cashier, json=payload)
        assert created_order.status_code == 200, created_order.text
        duplicate = c.post("/api/orders", headers=cashier, json=payload)
        assert duplicate.status_code == 200, duplicate.text
        assert created_order.json()["id"] == duplicate.json()["id"]
        stock_after = c.get("/api/sync", headers=cashier).json()["stock"]["beans"]
        assert stock_after < stock0
        assert len(c.get("/api/sync", headers=cashier).json()["orders"]) == 1
        finance = c.get("/api/reports/finance?days=7", headers=owner)
        assert finance.status_code == 200, finance.text
        assert finance.json()["expenses"] == 7000
        assert finance.json()["orders"] == 1
