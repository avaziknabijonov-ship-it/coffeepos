import os
import tempfile

os.environ["ALLOW_PUBLIC_REGISTRATION"] = "1"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def company(c, slug):
    r = c.post("/api/auth/register", json={"companyName": slug, "slug": slug, "ownerName": "Ega", "ownerPin": "1111"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def staff(c, owner, name, role, pin, slug):
    assert c.post("/api/staff", headers=owner, json={"name": name, "role": role, "pin": pin}).status_code == 200
    r = c.post("/api/auth/login", json={"company": slug, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


LATTE = {"productId": "latte", "size": "M", "modIds": [], "qty": 2}
CAKE = {"productId": "cheesecake", "size": "-", "modIds": [], "qty": 1}


def test_waiter_table_flow():
    with TestClient(app) as c:
        slug = "resto-kofe"
        owner = company(c, slug)
        waiter = staff(c, owner, "Ofitsiant Ali", "ofitsiant", "5555", slug)
        kassir = staff(c, owner, "Kassir Lola", "kassir", "6666", slug)
        chef = staff(c, owner, "Oshpaz Bek", "barista", "7777", slug)

        # workshops: desserts go to the kitchen, coffee stays on the default (bar) screen
        w = c.post("/api/workshops", headers=owner, json={"name": "Oshxona"}).json()
        assert c.patch("/api/categories/dessert/workshop", headers=owner, json={"workshop": w["id"]}).status_code == 200
        assert c.patch("/api/categories/dessert/workshop", headers=owner, json={"workshop": "nope"}).status_code == 404
        menu = c.get("/api/menu", headers=waiter).json()
        assert {"id": w["id"], "name": "Oshxona"} in menu["workshops"]
        assert next(x for x in menu["categories"] if x["id"] == "dessert")["workshop"] == w["id"]

        hall = c.post("/api/halls", headers=owner, json={"name": "Asosiy zal"}).json()
        table = c.post("/api/tables", headers=owner, json={"hallId": hall["id"], "name": "5", "seats": 4}).json()
        assert c.post("/api/tables", headers=waiter, json={"hallId": hall["id"], "name": "6"}).status_code == 403
        assert c.get("/api/halls", headers=waiter).json()[0]["tables"][0]["name"] == "5"

        # no shift yet
        assert c.post("/api/checks", headers=waiter, json={"tableId": table["id"], "guests": 2}).status_code == 409
        assert c.post("/api/shifts/open", headers=kassir, json={"openingCash": 0}).status_code == 200
        chk = c.post("/api/checks", headers=waiter, json={"tableId": table["id"], "guests": 2}).json()
        assert chk["tableName"] == "Asosiy zal · 5" and chk["waiter"] == "Ofitsiant Ali"

        r = c.put(f"/api/checks/{chk['id']}/items", headers=waiter, json={"items": [LATTE, CAKE]})
        assert r.status_code == 200, r.text
        assert r.json()["unsent"] == 3
        sent = c.post(f"/api/checks/{chk['id']}/send", headers=waiter)
        assert sent.status_code == 200, sent.text
        tickets = sent.json()["tickets"]
        assert {t["workshop"] for t in tickets} == {"", w["id"]}
        assert c.post(f"/api/checks/{chk['id']}/send", headers=waiter).status_code == 409

        # waiter cannot remove an item already sent; manager can
        assert c.put(f"/api/checks/{chk['id']}/items", headers=waiter, json={"items": [CAKE]}).status_code == 403
        # adding one more latte sends only the extra one
        c.put(f"/api/checks/{chk['id']}/items", headers=waiter, json={"items": [{**LATTE, "qty": 3}, CAKE]})
        extra = c.post(f"/api/checks/{chk['id']}/send", headers=waiter).json()["tickets"]
        assert len(extra) == 1 and extra[0]["items"][0]["qty"] == 1

        # kitchen screen sees tickets in sync and moves them forward
        sync = c.get("/api/sync", headers=chef).json()
        assert len(sync["tickets"]) == 3 and sync["checks"][0]["id"] == chk["id"]
        tid = tickets[0]["id"]
        assert c.patch(f"/api/tickets/{tid}", headers=chef, json={"status": "ready"}).status_code == 409
        assert c.patch(f"/api/tickets/{tid}", headers=chef, json={"status": "preparing"}).status_code == 200
        assert c.patch(f"/api/tickets/{tid}", headers=waiter, json={"status": "ready"}).status_code == 403
        assert c.patch(f"/api/tickets/{tid}", headers=chef, json={"status": "ready"}).json()["readyAt"]
        assert c.patch(f"/api/tickets/{tid}", headers=waiter, json={"status": "done"}).status_code == 200

        # waiter can't take payment; cashier closes the bill into a paid order
        pay = {"payment": "karta", "clientKey": "check-pay-0000001"}
        assert c.post(f"/api/checks/{chk['id']}/pay", headers=waiter, json=pay).status_code == 403
        before = c.get("/api/sync", headers=owner).json()["stock"]
        r = c.post(f"/api/checks/{chk['id']}/pay", headers=kassir, json=pay)
        assert r.status_code == 200, r.text
        order = r.json()
        assert order["status"] == "done" and order["customer"] == "Asosiy zal · 5"
        assert sum(i["qty"] for i in order["items"]) == 4
        after = c.get("/api/sync", headers=owner).json()
        assert after["stock"]["cheesecake"] == before["cheesecake"] - 1
        assert after["checks"] == []
        # repeat payment is idempotent
        assert c.post(f"/api/checks/{chk['id']}/pay", headers=kassir, json=pay).json()["id"] == order["id"]
        assert c.put(f"/api/checks/{chk['id']}/items", headers=waiter, json={"items": [CAKE]}).status_code == 409

        # void: allowed for the waiter only while nothing was sent
        chk2 = c.post("/api/checks", headers=waiter, json={"tableId": table["id"]}).json()
        c.put(f"/api/checks/{chk2['id']}/items", headers=waiter, json={"items": [CAKE]})
        assert c.post(f"/api/checks/{chk2['id']}/void", headers=waiter, json={"reason": "mijoz ketdi"}).status_code == 200
        chk3 = c.post("/api/checks", headers=waiter, json={"tableId": table["id"]}).json()
        c.put(f"/api/checks/{chk3['id']}/items", headers=waiter, json={"items": [CAKE]})
        c.post(f"/api/checks/{chk3['id']}/send", headers=waiter)
        assert c.post(f"/api/checks/{chk3['id']}/void", headers=waiter, json={"reason": "mijoz ketdi"}).status_code == 403
        assert c.delete(f"/api/tables/{table['id']}", headers=owner).status_code == 409
        assert c.post(f"/api/checks/{chk3['id']}/void", headers=owner, json={"reason": "rahbar qarori"}).status_code == 200
        assert c.delete(f"/api/halls/{hall['id']}", headers=owner).status_code == 409
        assert c.delete(f"/api/tables/{table['id']}", headers=owner).status_code == 200

        # other companies can't see or touch the bill
        other = company(c, "resto-kofe-2")
        assert c.post(f"/api/checks/{chk3['id']}/send", headers=other).status_code == 404
