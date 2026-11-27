"""Low-stock alerts sent to a Telegram chat through the company's own bot."""
import json
import logging
import threading
import urllib.request
from collections.abc import Iterable

log = logging.getLogger("coffeepos.notify")


def low_stock_crossings(before: dict[str, float], after: Iterable) -> list[dict]:
    """Ingredients whose stock was at/above the minimum and is now below it."""
    out = []
    for ing in after:
        prev = before.get(ing.key)
        if prev is None or ing.min <= 0:
            continue
        if prev >= ing.min and ing.stock < ing.min:
            out.append({"name": ing.name, "stock": ing.stock, "min": ing.min, "unit": ing.unit})
    return out


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") if abs(x - round(x)) < 0.01 else f"{x:.1f}"


def format_message(company: str, crossed: list[dict]) -> str:
    lines = [f"⚠️ {company}: qoldiq minimumdan kam"]
    for c in crossed:
        lines.append(f"• {c['name']}: {_fmt(c['stock'])} {c['unit']} (min {_fmt(c['min'])})")
    return "\n".join(lines)


def _post(token: str, chat: str, text: str) -> None:
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat, "text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=8).close()
    except Exception as exc:  # alerts must never break a sale
        log.warning("Telegram alert failed: %s", type(exc).__name__)


def send_low_stock_alert(token: str, chat: str, company: str, crossed: list[dict]) -> None:
    threading.Thread(target=_post, args=(token, chat, format_message(company, crossed)), daemon=True).start()
