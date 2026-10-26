import pytest
from datetime import datetime, time, timezone
from app.operations import inventory_variance, low_stock, cash_difference, profit_loss, happy_hour_active


def test_inventory():
    r = inventory_variance([
        {"ingredient": "milk", "expected": 10, "counted": 8, "unit_cost": 1000},
        {"ingredient": "coffee", "expected": 3, "counted": 4, "unit_cost": 2000},
    ])
    assert r["shortage"] == 2000 and r["surplus"] == 2000


def test_duplicate_inventory():
    line = {"ingredient": "milk", "expected": 1, "counted": 1, "unit_cost": 1}
    with pytest.raises(ValueError):
        inventory_variance([line, line])


def test_low_stock():
    assert low_stock({"milk": 2, "coffee": 5}, {"milk": 2, "coffee": 3}) == ["milk"]


def test_cash_difference():
    assert cash_difference(100, 500, 50, 20, 530) == 0
    assert cash_difference(100, 500, 50, 20, 520) == -10


def test_profit_loss():
    assert profit_loss(1000, 100, 400, 200) == {
        "net_revenue": 900, "gross_profit": 500, "operating_result": 300,
    }


def test_invalid_refunds():
    with pytest.raises(ValueError):
        profit_loss(100, 101, 0, 0)


def test_happy_hour():
    now = datetime(2026, 10, 27, 8, 30, tzinfo=timezone.utc)
    assert happy_hour_active(now, time(12), time(14))
    assert not happy_hour_active(now, time(14), time(16))


def test_overnight():
    now = datetime(2026, 10, 27, 18, 30, tzinfo=timezone.utc)
    assert happy_hour_active(now, time(22), time(2))
