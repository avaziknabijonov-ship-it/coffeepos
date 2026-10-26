"""Pure POS calculations; integration with endpoints is a separate step."""
from datetime import datetime, time
from zoneinfo import ZoneInfo


def inventory_variance(lines):
    seen = set()
    out = []
    shortage = surplus = 0
    for item in lines:
        key, expected, counted, cost = (item[k] for k in ("ingredient", "expected", "counted", "unit_cost"))
        if key in seen or not key or min(expected, counted, cost) < 0:
            raise ValueError("Invalid inventory line")
        seen.add(key)
        delta = counted - expected
        value = round(abs(delta) * cost)
        shortage += value if delta < 0 else 0
        surplus += value if delta > 0 else 0
        out.append({"ingredient": key, "delta": delta, "value": value})
    return {"lines": out, "shortage": shortage, "surplus": surplus}


def low_stock(quantities, minimums):
    if any(v < 0 for v in quantities.values()) or any(v < 0 for v in minimums.values()):
        raise ValueError("Negative stock or minimum")
    return sorted(k for k, qty in quantities.items() if k in minimums and qty <= minimums[k])


def cash_difference(opening, sales, refunds, expenses, closing):
    amounts = (opening, sales, refunds, expenses, closing)
    if any(type(x) is not int or x < 0 for x in amounts):
        raise ValueError("Invalid amount")
    return closing - (opening + sales - refunds - expenses)


def profit_loss(revenue, refunds, cogs, expenses):
    amounts = (revenue, refunds, cogs, expenses)
    if any(type(x) is not int or x < 0 for x in amounts) or refunds > revenue:
        raise ValueError("Invalid amount")
    net = revenue - refunds
    return {"net_revenue": net, "gross_profit": net - cogs, "operating_result": net - cogs - expenses}


def happy_hour_active(now: datetime, start: time, end: time, tz="Asia/Tashkent"):
    if now.tzinfo is None or start == end:
        raise ValueError("Timezone-aware datetime and nonempty interval required")
    local = now.astimezone(ZoneInfo(tz)).time().replace(tzinfo=None)
    return start <= local < end if start < end else local >= start or local < end
