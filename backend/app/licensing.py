"""Server-side tenant license rules.

No client clock, PIN, or request body can override these checks.
An expired or suspended tenant retains read-only access to its own records.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from typing import Literal

from .db import Subscription, now_ms


Plan = Literal["monthly", "yearly"]


def add_calendar_period(base_ms: int, period: Plan) -> int:
    """Advance a calendar month/year in UTC (not 30/365 fixed days).

    Preserve the hour and minute; clamp the day for short months or Feb 29.
    """
    date = datetime.fromtimestamp(base_ms / 1000, tz=timezone.utc)
    if period == "monthly":
        year = date.year + (date.month // 12)
        month = date.month % 12 + 1
    elif period == "yearly":
        year, month = date.year + 1, date.month
    else:
        raise ValueError("Unsupported billing period")
    day = min(date.day, monthrange(year, month)[1])
    return int(date.replace(year=year, month=month, day=day).timestamp() * 1000)


def subscription_status(sub: Subscription | None, current_ms: int | None = None) -> str:
    now = now_ms() if current_ms is None else current_ms
    if sub is None:
        return "unconfigured"
    if sub.status == "suspended":
        return "suspended"
    if sub.status == "expired":
        return "expired"
    if sub.status == "trial":
        return "trial" if sub.trial_ends_at is not None and sub.trial_ends_at > now else "expired"
    if sub.status == "active":
        if sub.current_period_ends_at is not None and sub.current_period_ends_at > now:
            return "active"
        if sub.grace_ends_at is not None and sub.grace_ends_at > now:
            return "grace"
        return "expired"
    if sub.status == "grace":
        return "grace" if sub.grace_ends_at is not None and sub.grace_ends_at > now else "expired"
    return "unconfigured"


def may_write(status: str) -> bool:
    return status in ("trial", "active", "grace")


def subscription_payload(sub: Subscription | None, current_ms: int | None = None) -> dict:
    now = now_ms() if current_ms is None else current_ms
    status = subscription_status(sub, now)
    until = None
    if sub:
        if status == "trial":
            until = sub.trial_ends_at
        elif status == "active":
            until = sub.current_period_ends_at
        elif status == "grace":
            until = sub.grace_ends_at
    return {
        "status": status,
        "plan": sub.plan if sub else None,
        "canWrite": may_write(status),
        "expiresAt": until,
        "trialEndsAt": sub.trial_ends_at if sub else None,
        "currentPeriodEndsAt": sub.current_period_ends_at if sub else None,
        "graceEndsAt": sub.grace_ends_at if sub else None,
        "serverTime": now,
    }
