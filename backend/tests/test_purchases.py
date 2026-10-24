from fastapi.testclient import TestClient
from app.main import app

def test_invoice_cancel_restores_stock():
    with TestClient(app) as c:
        auth = c.post("/api/auth/login", json={"company":"demo","pin":"1111"})
        assert auth.status_code == 200
        h = {"Authorization":"Bearer " + auth.json()["token"]}
        before = c.get("/api/sync", headers=h).json()["stock"]["beans"]
        r = c.post("/api/purchases", headers=h, json={
            "number":"CANCEL-TEST-001","supplier":"Test",
            "received_at":1780000000000,"payment_status":"paid",
            "lines":[{"ing":"beans","qty":50,"unit_price":100}]})
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        assert c.get("/api/sync", headers=h).json()["stock"]["beans"] == before + 50
        r = c.post("/api/purchases/" + str(pid) + "/cancel", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"
        assert c.get("/api/sync", headers=h).json()["stock"]["beans"] == before
        assert c.post("/api/purchases/" + str(pid) + "/cancel", headers=h).status_code == 409
