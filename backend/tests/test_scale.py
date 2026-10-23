"""Regression test for 100+ independent coffee-shop tenants.
Runs with the integration test suite's isolated SQLite database.
"""
from fastapi.testclient import TestClient
from app.main import app


def test_120_company_isolation():
    with TestClient(app) as client:
        first_headers = None
        for n in range(120):
            data = {
                "companyName": f"Coffee Shop {n}",
                "slug": f"coffeeshop-{n:03d}",
                "ownerName": "Owner",
                "ownerPin": f"{1000 + n}",
            }
            response = client.post("/api/auth/register", json=data)
            assert response.status_code == 200, (n, response.text)
            headers = {"Authorization": "Bearer " + response.json()["token"]}
            assert client.get("/api/expenses", headers=headers).json() == []
            if n == 0:
                first_headers = headers
                created = client.post("/api/expenses", headers=headers, json={
                    "amount": 7000, "category": "Transport", "payment": "cash"
                })
                assert created.status_code == 200
            else:
                assert client.get("/api/expenses", headers=headers).json() == []
        assert len(client.get("/api/expenses", headers=first_headers).json()) == 1
