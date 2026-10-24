from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from app.main import app


def test_monthly_payroll_manual_days_and_advances():
    month = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m")
    with TestClient(app) as c:
        registered = c.post("/api/auth/register", json={
            "companyName": "Payroll Cafe", "slug": "payroll-cafe-test",
            "ownerName": "Owner", "ownerPin": "7311"
        })
        assert registered.status_code == 200, registered.text
        owner = {"Authorization": "Bearer " + registered.json()["token"]}
        new_staff = c.post("/api/staff", headers=owner, json={
            "name": "Barista", "role": "barista", "pin": "7312"
        })
        assert new_staff.status_code == 200
        staff_id = new_staff.json()["id"]
        entry = c.put(f"/api/payroll/{staff_id}/{month}", headers=owner, json={
            "monthly_salary": 2600000, "standard_days": 26,
            "worked_days": 13, "deductions": 50000, "note": "Qisman oy"
        })
        assert entry.status_code == 200, entry.text
        advance = c.post("/api/staff-payments", headers=owner, json={
            "staff_id": staff_id, "amount": 100000, "note": "Avans"
        })
        assert advance.status_code == 200, advance.text
        report = c.get("/api/payroll?month=" + month, headers=owner)
        assert report.status_code == 200, report.text
        row = next(x for x in report.json()["items"] if x["staffId"] == staff_id)
        assert row["earned"] == 1300000
        assert row["deductions"] == 50000
        assert row["paid"] == 100000
        assert row["toPay"] == 1150000
        assert c.get("/api/payroll?month=bad", headers=owner).status_code == 422
