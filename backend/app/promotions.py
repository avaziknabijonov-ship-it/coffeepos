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


def choose_promotion(rules, now):
    active = [rule for rule in rules if is_active(rule, now)]
    return min(active, key=lambda rule: (-rule.priority, rule.id)) if active else None


def discount_amount(subtotal, percent):
    # Preserve existing 100 UZS rounding with integer arithmetic and ties-to-even,
    # while strictly capping the discount at the requested percentage.
    if type(subtotal) is not int or subtotal < 0 or type(percent) is not int or not 0 <= percent <= 50:
        raise ValueError('Invalid discount')
    quotient, remainder = divmod(subtotal * percent, 10000)
    rounded = quotient + (remainder > 5000 or (remainder == 5000 and quotient % 2 == 1))
    return min(rounded * 100, subtotal * percent // 100)
