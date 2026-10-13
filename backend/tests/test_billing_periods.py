"""Calendar-based subscription calculations."""
from datetime import datetime, timezone
from app.licensing import add_calendar_period


def ms(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)


def test_month_end_clamps_to_last_day():
    assert add_calendar_period(ms("2026-01-31T10:15:00"), "monthly") == ms("2026-02-28T10:15:00")
    assert add_calendar_period(ms("2028-01-31T10:15:00"), "monthly") == ms("2028-02-29T10:15:00")
    assert add_calendar_period(ms("2026-12-31T10:15:00"), "monthly") == ms("2027-01-31T10:15:00")


def test_years_handle_leap_days():
    assert add_calendar_period(ms("2028-02-29T12:30:00"), "yearly") == ms("2029-02-28T12:30:00")
    assert add_calendar_period(ms("2026-10-13T11:00:00"), "yearly") == ms("2027-10-13T11:00:00")
