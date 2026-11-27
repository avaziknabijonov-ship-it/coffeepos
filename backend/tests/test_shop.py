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


def test_weighted_goods_barcodes_and_refunds():
    with TestClient(app) as c:
        h = company(c, "shop-kofe")
        ing = c.post("/api/ingredients", headers=h, json={"name": "Kofe doni (vazn)", "unit": "g", "cost": 200, "min": 0}).json()
        c.post("/api/purchases", headers=h, json={"number": "S1", "supplier": "X", "received_at": 1780000000000,
                                                   "payment_status": "paid", "lines": [{"ing": ing["id"], "qty": 5000, "unit_price": 200}]})
        weighted = {"cat": "dessert", "name": "Kofe doni 1 kg", "weighted": True,
                    "sizes": [{"code": "-", "price": 300000, "barcode": "00042", "recipe": [{"ing": ing["id"], "qty": 1000}]}]}
        r = c.post("/api/products", headers=h, json=weighted)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        assert r.json()["weighted"] is True and r.json()["sizes"][0]["barcode"] == "00042"

        bottle = {"cat": "dessert", "name": "Suv 0.5", "sizes": [{"code": "-", "price": 4000, "barcode": "4780000000017", "recipe": []}]}
        assert c.post("/api/products", headers=h, json=bottle).status_code == 200
        dup = {**bottle, "name": "Suv nusxa"}
        assert c.post("/api/products", headers=h, json=dup).status_code == 409

        assert c.post("/api/shifts/open", headers=h, json={"openingCash": 100000}).status_code == 200
        no_weight = {"items": [{"productId": pid, "size": "-", "modIds": [], "qty": 1}], "payment": "naqd"}
        assert c.post("/api/orders", headers=h, json=no_weight).status_code == 400
        espresso_weight = {"items": [{"productId": "espresso", "size": "-", "modIds": [], "qty": 1, "weight": 1}], "payment": "naqd"}
        assert c.post("/api/orders", headers=h, json=espresso_weight).status_code == 400

        sale = {"items": [{"productId": pid, "size": "-", "modIds": [], "qty": 1, "weight": 0.25},
                          {"productId": "espresso", "size": "-", "modIds": [], "qty": 3}], "payment": "naqd"}
        o = c.post("/api/orders", headers=h, json=sale)
        assert o.status_code == 200, o.text
        o = o.json()
        coffee = o["items"][0]
        assert coffee["unitPrice"] == 75000 and coffee["weight"] == 0.25 and coffee["size"] == "0.250 kg"
        assert c.get("/api/sync", headers=h).json()["stock"][ing["id"]] == 5000 - 250

        # partial refund: 1 espresso back
        esp = o["items"][1]
        assert c.post(f"/api/orders/{o['id']}/refund", headers=h, json={"lines": [{"key": esp["key"], "qty": 4}], "reason": "xato"}).status_code == 409
        r1 = c.post(f"/api/orders/{o['id']}/refund", headers=h, json={"lines": [{"key": esp["key"], "qty": 1}], "reason": "sovuq edi"})
        assert r1.status_code == 200, r1.text
        assert r1.json()["amount"] == esp["unitPrice"]
        info = c.get(f"/api/orders/{o['id']}/refunds", headers=h).json()
        assert info["remaining"][esp["key"]] == 2 and info["refundedAmount"] == esp["unitPrice"]
        # cancelling a receipt that already had a return is refused
        assert c.post(f"/api/orders/{o['id']}/cancel", headers=h, json={"reason": "test bekor"}).status_code == 409

        # refund the rest: total refunded equals the receipt total exactly, stock fully restored
        rest = [{"key": coffee["key"], "qty": 1}, {"key": esp["key"], "qty": 2}]
        r2 = c.post(f"/api/orders/{o['id']}/refund", headers=h, json={"lines": rest, "reason": "mijoz qaytardi"})
        assert r2.status_code == 200, r2.text
        assert r1.json()["amount"] + r2.json()["amount"] == o["total"]
        assert c.get("/api/sync", headers=h).json()["stock"][ing["id"]] == 5000
        assert c.post(f"/api/orders/{o['id']}/refund", headers=h, json={"lines": [{"key": esp["key"], "qty": 1}], "reason": "yana"}).status_code == 409

        shift = c.get("/api/shifts/current", headers=h).json()
        assert shift["refunds"] == o["total"] and shift["revenue"] == 0
        assert shift["expectedCash"] == 100000
        sales = c.get("/api/reports/sales", headers=h).json()
        assert sales["totals"]["refunds"] == o["total"] and sales["totals"]["revenue"] == 0
        assert c.get("/api/reports/daily?days=1", headers=h).json()[-1]["revenue"] == 0

        # kassir without permission can't refund
        c.post("/api/staff", headers=h, json={"name": "K", "role": "kassir", "pin": "2468"})
        k = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"company": "shop-kofe", "pin": "2468"}).json()["token"]}
        o2 = c.post("/api/orders", headers=k, json={"items": [{"productId": "espresso", "size": "-", "modIds": [], "qty": 1}], "payment": "karta"}).json()
        assert c.post(f"/api/orders/{o2['id']}/refund", headers=k, json={"lines": [{"key": o2["items"][0]["key"], "qty": 1}], "reason": "xato"}).status_code == 403
