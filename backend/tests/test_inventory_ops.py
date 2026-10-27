"""G2: branch low-stock dedupe, stock transfers and stocktake approval."""
from uuid import uuid4

from fastapi.testclient import TestClient

from helpers import at, new_company, staff_login
from test_api import app


def stock(c, h):
    return c.get("/api/sync", headers=h).json()["stock"]


def receive_beans(c, h, qty):
    current = stock(c, h)["beans"]
    r = c.post("/api/inventories", headers=h, json={"lines": [{"ing": "beans", "counted": current + qty}]})
    assert r.status_code == 200, r.text


def test_transfer_lifecycle_is_atomic_and_single_receive():
    with TestClient(app) as c:
        h, slug = new_company(c, "trf")
        second = c.post("/api/branches", json={"name": "Chilonzor"}, headers=h).json()["id"]
        main_id = c.get("/api/branches", headers=h).json()["current"]
        receive_beans(c, h, 1000)
        body = {"clientKey": uuid4().hex, "toBranchId": second, "lines": [{"ing": "beans", "qty": 400}]}
        assert c.post("/api/transfers", headers=h, json={**body, "clientKey": uuid4().hex,
                                                       "lines": [{"ing": "beans", "qty": 5000}]}).status_code == 409
        assert c.post("/api/transfers", headers=h, json={**body, "toBranchId": main_id}).status_code == 422
        sent = c.post("/api/transfers", headers=h, json=body)
        assert sent.status_code == 201 and sent.json()["status"] == "in_transit"
        assert c.post("/api/transfers", headers=h, json=body).json()["id"] == sent.json()["id"]
        assert stock(c, h)["beans"] == 600 and stock(c, at(h, second))["beans"] == 0
        tid = sent.json()["id"]
        assert c.post(f"/api/transfers/{tid}/receive", headers=h, json={}).status_code == 403
        assert c.post(f"/api/transfers/{tid}/receive", headers=at(h, second), json={
            "lines": [{"ing": "beans", "qty": 401}]}).status_code == 422
        got = c.post(f"/api/transfers/{tid}/receive", headers=at(h, second),
                     json={"lines": [{"ing": "beans", "qty": 390}]})
        assert got.status_code == 200 and got.json()["receivedLines"][0]["loss"] == 10
        assert c.post(f"/api/transfers/{tid}/receive", headers=at(h, second), json={}).status_code == 409
        assert stock(c, at(h, second))["beans"] == 390
        assert c.post(f"/api/transfers/{tid}/cancel", headers=h).status_code == 409
        other = c.post("/api/transfers", headers=h, json={**body, "clientKey": uuid4().hex}).json()
        assert c.post(f"/api/transfers/{other['id']}/cancel", headers=h).json()["status"] == "cancelled"
        assert stock(c, h)["beans"] == 600
        assert len(c.get("/api/transfers", headers=at(h, second)).json()) == 2
        actions = {e["action"] for e in c.get("/api/audit", headers=h).json()["items"]}
        assert {"transfer.dispatch", "transfer.receive", "transfer.cancel"} <= actions
        kassir, _ = staff_login(c, h, slug, "kassir", "1357")
        assert c.post("/api/transfers", headers=kassir, json={**body, "clientKey": uuid4().hex}).status_code == 403
        intruder, _ = new_company(c, "trx")
        assert c.post(f"/api/transfers/{tid}/receive", headers=intruder, json={}).status_code == 404
        assert c.post("/api/transfers", headers=intruder, json={**body, "clientKey": uuid4().hex}).status_code == 404


def test_branch_low_stock_thresholds_and_deduplicated_notifications():
    with TestClient(app) as c:
        h, _ = new_company(c, "low")
        second = c.post("/api/branches", json={"name": "Sergeli"}, headers=h).json()["id"]
        assert c.put(f"/api/branches/{second}/stock/beans/min", headers=h, json={"min": 100}).status_code == 200
        alerts = c.get("/api/stock/alerts", headers=at(h, second)).json()["items"]
        assert [a["id"] for a in alerts if a["id"] == "beans"] == ["beans"]
        first = c.get("/api/stock/notifications", headers=at(h, second)).json()["items"]
        again = c.get("/api/stock/notifications", headers=at(h, second)).json()["items"]
        beans = [n for n in again if n["ingredient"] == "beans"]
        assert len(beans) == 1 and [n["id"] for n in first] == [n["id"] for n in again]
        assert all(n["branchId"] != second for n in c.get("/api/stock/notifications", headers=h).json()["items"])
        assert c.post("/api/inventories", headers=at(h, second),
                      json={"lines": [{"ing": "beans", "counted": 500}]}).status_code == 200
        assert all(n["ingredient"] != "beans" for n in
                   c.get("/api/stock/notifications", headers=at(h, second)).json()["items"])
        assert c.post("/api/inventories", headers=at(h, second),
                      json={"lines": [{"ing": "beans", "counted": 50}]}).status_code == 200
        history = c.get("/api/stock/notifications?include_resolved=true", headers=at(h, second)).json()["items"]
        assert len([n for n in history if n["ingredient"] == "beans"]) == 2


def test_stocktake_approval_applies_signed_difference_once():
    with TestClient(app) as c:
        h, slug = new_company(c, "inv")
        receive_beans(c, h, 1000)
        admin, aid = staff_login(c, h, slug, "admin", "2468")
        pending = c.post("/api/inventories", headers=admin, json={
            "lines": [{"ing": "beans", "counted": 950}], "requireApproval": True})
        assert pending.status_code == 200 and pending.json()["status"] == "pending"
        assert stock(c, h)["beans"] == 1000
        iid = pending.json()["id"]
        assert c.post(f"/api/inventories/{iid}/approve", headers=admin).status_code == 403
        c.post("/api/shifts/open", json={"openingCash": 0}, headers=h)
        sold = c.post("/api/orders", headers=h, json={"items": [{"productId": "espresso", "size": "-", "qty": 1}],
                                                     "payment": "karta"}).json()
        used = sum(u["qty"] for line in sold["items"] for u in line["consumption"] if u["ing"] == "beans")
        approved = c.post(f"/api/inventories/{iid}/approve", headers=h)
        assert approved.status_code == 200 and approved.json()["approvedBy"] == "Owner"
        assert stock(c, h)["beans"] == 1000 - used - 50
        assert c.post(f"/api/inventories/{iid}/approve", headers=h).status_code == 409
        rejected = c.post("/api/inventories", headers=admin, json={
            "lines": [{"ing": "beans", "counted": 1}], "requireApproval": True}).json()
        assert c.post(f"/api/inventories/{rejected['id']}/reject", headers=h).json()["status"] == "rejected"
        assert stock(c, h)["beans"] == 1000 - used - 50
        report = c.get("/api/reports/inventory-variance", headers=h).json()
        beans = next(r for r in report["items"] if r["ingredient"] == "beans")
        assert beans["diff"] == 1000 - 50 and beans["counts"] == 2  # receiving count + approved stocktake
        assert report["surplus"] == beans["value"] and report["shortage"] == 0
