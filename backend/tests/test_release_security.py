"""Release smoke tests: server-side permissions and tenant separation.

All records are created in the isolated pytest SQLite database, never in the
live MasterCoffee database.
"""

import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def register(client: TestClient, slug: str, pin: str = "1234") -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "companyName": "QA " + slug,
            "slug": slug,
            "ownerName": "Test Owner",
            "ownerPin": pin,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def login(client: TestClient, slug: str, pin: str) -> dict:
    response = client.post("/api/auth/login", json={"company": slug, "pin": pin})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_permissions_are_enforced_by_api_not_only_hidden_in_menu():
    with TestClient(app) as client:
        slug = "roles-security-qa"
        owner = register(client, slug)
        assert client.post(
            "/api/staff",
            json={"name": "Kassir QA", "role": "kassir", "pin": "2345"},
            headers=owner,
        ).status_code == 200
        assert client.post(
            "/api/staff",
            json={"name": "Barista QA", "role": "barista", "pin": "3456"},
            headers=owner,
        ).status_code == 200
        cashier = login(client, slug, "2345")
        barista = login(client, slug, "3456")

        assert client.get("/api/staff").status_code == 401
        assert client.get("/api/sync").status_code == 401

        for path in (
            "/api/staff",
            "/api/debts",
            "/api/reports/daily",
            "/api/reports/profit",
            "/api/salary?month=2026-10",
            "/api/inventories",
            "/api/reports/losses",
        ):
            assert client.get(path, headers=cashier).status_code == 403, path

        for path, body in (
            ("/api/stock", {"ing": "beans", "qty": 10, "reason": "intake"}),
            ("/api/inventories", {"lines": [{"ing": "beans", "counted": 100}]}),
            ("/api/staff", {"name": "Bad", "role": "admin", "pin": "9876"}),
            ("/api/salary/entries", {"staffId": 1, "kind": "payment", "amount": 1}),
        ):
            assert client.post(path, json=body, headers=cashier).status_code == 403, path

        for path in ("/api/expenses", "/api/staff", "/api/staff/expense-recipients"):
            assert client.get(path, headers=barista).status_code == 403, path
        assert client.post(
            "/api/shifts/open", json={"openingCash": 0}, headers=barista
        ).status_code == 403
        assert client.post(
            "/api/orders",
            json={"items": [{"productId": "latte", "size": "M"}], "payment": "naqd"},
            headers=barista,
        ).status_code == 403
        assert client.post(
            "/api/expenses",
            json={"category": "Transport", "amount": 100, "method": "naqd"},
            headers=barista,
        ).status_code == 403


def test_tenant_data_and_mutation_are_isolated():
    with TestClient(app) as client:
        a = register(client, "isolation-alpha-qa")
        a_staff = client.get("/api/staff", headers=a).json()[0]["id"]
        beans_before = next(
            i["stock"] for i in client.get("/api/menu", headers=a).json()["ingredients"]
            if i["id"] == "beans"
        )
        assert client.post(
            "/api/shifts/open", json={"openingCash": 20000}, headers=a
        ).status_code == 200
        shift_id = client.get("/api/shifts/current", headers=a).json()["shift"]["id"]

        order = client.post(
            "/api/orders",
            json={
                "items": [{"productId": "latte", "size": "M", "qty": 1}],
                "payment": "qarz",
                "customer": "Alpha Guest",
            },
            headers=a,
        )
        assert order.status_code == 200, order.text
        debt_id = client.get("/api/debts", headers=a).json()[0]["id"]
        assert client.post(
            "/api/expenses",
            json={"amount": 1000, "category": "Transport", "method": "naqd"},
            headers=a,
        ).status_code == 200

        b = register(client, "isolation-bravo-qa", pin="4567")
        assert client.get("/api/debts", headers=b).json() == []
        assert client.get("/api/expenses", headers=b).json() == []
        assert client.get("/api/sync", headers=b).json()["orders"] == []
        assert client.get("/api/shifts/current", headers=b).json() is None
        assert client.get("/api/inventories", headers=b).json() == []
        b_beans = next(
            i["stock"] for i in client.get("/api/menu", headers=b).json()["ingredients"]
            if i["id"] == "beans"
        )
        assert b_beans == beans_before

        assert client.get(f"/api/shifts/{shift_id}/report", headers=b).status_code == 404
        assert client.get(f"/api/debts/{debt_id}/payments", headers=b).status_code == 404
        assert client.post(
            f"/api/debts/{debt_id}/payments",
            json={"amount": 1, "method": "naqd"},
            headers=b,
        ).status_code == 404
        assert client.patch(
            f"/api/staff/{a_staff}/salary",
            json={"salaryType": "daily", "salaryRate": 5},
            headers=b,
        ).status_code == 404
        assert client.get("/api/debts", headers=a).json()[0]["remaining"] == order.json()["total"]
