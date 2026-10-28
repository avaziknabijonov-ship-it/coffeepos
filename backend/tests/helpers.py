"""Shared helpers for isolated per-test tenants."""
from uuid import uuid4


def new_company(client, prefix="t"):
    slug = f"{prefix}-" + uuid4().hex[:12]
    response = client.post("/api/auth/register", json={
        "companyName": f"{prefix} test", "slug": slug, "ownerName": "Owner", "ownerPin": "1111",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}, slug


def staff_login(client, owner, slug, role, pin, name=None):
    created = client.post("/api/staff", json={"name": name or f"{role}-{pin}", "role": role, "pin": pin}, headers=owner)
    assert created.status_code == 200, created.text
    token = client.post("/api/auth/login", json={"company": slug, "pin": pin})
    assert token.status_code == 200, token.text
    return {"Authorization": f"Bearer {token.json()['token']}"}, created.json()["id"]


def at(headers, branch_id):
    return {**headers, "X-Branch-Id": str(branch_id)}


LATTE = {"items": [{"productId": "latte", "size": "M", "modIds": [], "qty": 1}], "payment": "naqd"}
