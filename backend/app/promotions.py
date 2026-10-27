"""Whole-order Happy Hour: non-stacking, deterministic, server-local schedule."""
from datetime import datetime, time, timedelta


def is_active(rule, now):
    if now.tzinfo is None:
        raise ValueError('Timezone-aware datetime required')
    if not rule.active:
        return False
    start, end = time.fromisoformat(rule.start_time), time.fromisoformat(rule.end_time)
    current = now.time().replace(tzinfo=None)
    if start == end:
        return False
    if start < end:
        return now.weekday() in rule.weekdays and start <= current < end
    # Weekday means the day on which the overnight promotion starts.
    day = now if current >= start else now - timedelta(days=1)
    return day.weekday() in rule.weekdays and (current >= start or current < end)


def choose_promotion(rules, now, branch_id=None):
    """Company-wide rules (branch_id None) apply everywhere; branch rules only in their branch."""
    active = [rule for rule in rules if is_active(rule, now)
              and getattr(rule, 'branch_id', None) in (None, branch_id)]
    return min(active, key=lambda rule: (-rule.priority, rule.id)) if active else None


def capped_discount(subtotal, percent, cap=0):
    """Percentage discount limited by an optional absolute cap (0 = no cap)."""
    amount = discount_amount(subtotal, percent)
    return min(amount, cap) if cap and cap > 0 else amount


def discount_amount(subtotal, percent):
    # Preserve existing 100 UZS rounding with integer arithmetic and ties-to-even,
    # while strictly capping the discount at the requested percentage.
    if type(subtotal) is not int or subtotal < 0 or type(percent) is not int or not 0 <= percent <= 50:
        raise ValueError('Invalid discount')
    quotient, remainder = divmod(subtotal * percent, 10000)
    rounded = quotient + (remainder > 5000 or (remainder == 5000 and quotient % 2 == 1))
    return min(rounded * 100, subtotal * percent // 100)
