"""Regression test for 100+ independent coffee-shop tenants.
Uses a fresh local SQLite database and does not contact the production VPS.
"""
import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp()) / "scale.sqlite3")
os.environ["SEED_DEMO"] = "0"
os.environ["ENFORCE_LICENSES"] = "0"
os.environ["ALLOW_PUBLIC_REGISTRATION"] = "1"

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
