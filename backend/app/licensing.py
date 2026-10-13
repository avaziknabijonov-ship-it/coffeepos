"""Server-side tenant license rules.

No client clock, PIN, or request body can override these checks.
An expired or suspended tenant retains read-only access to its own records.
"""
from __future__ import annotations

from .db import Subscription, now_ms


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
        "canWrite": may_write(status),
        "expiresAt": until,
        "trialEndsAt": sub.trial_ends_at if sub else None,
        "currentPeriodEndsAt": sub.current_period_ends_at if sub else None,
        "graceEndsAt": sub.grace_ends_at if sub else None,
        "serverTime": now,
    }
