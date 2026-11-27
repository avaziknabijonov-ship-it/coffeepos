import math

from fastapi import HTTPException

from .db import Ingredient, Modifier, Product
from .seed import DEFAULT_MILK


def apply_effect(lines: list[dict], effect: dict) -> list[dict]:
    kind = effect.get("type")
    if kind == "swap":
        return [{**l, "ing": effect["to"]} if l["ing"] == effect["from"] else l for l in lines]
    if kind == "add":
        return [*lines, {"ing": effect["ing"], "qty": effect["qty"]}]
    return lines


def build_item(
    product: Product,
    size_code: str,
    mod_keys: list[str],
    qty: int,
    mods_by_key: dict[str, Modifier],
    ings_by_key: dict[str, Ingredient],
) -> dict:
    if not product.active:
        raise HTTPException(400, f"{product.name} stop-listda")
    size = next((s for s in product.sizes if s["code"] == size_code), None)
    if size is None:
        raise HTTPException(400, f"{product.name}: o'lcham topilmadi")
    if qty < 1 or qty > 99:
        raise HTTPException(400, "Miqdor noto'g'ri")

    mods: list[Modifier] = []
    for key in dict.fromkeys(mod_keys):
        if key == DEFAULT_MILK:
            continue
        mod = mods_by_key.get(key)
        if mod is None or mod.group not in product.mods:
            raise HTTPException(400, f"{product.name}: qo'shimcha mos emas")
        mods.append(mod)
    for group in ("milk", "shot"):
        if sum(1 for m in mods if m.group == group) > 1:
            raise HTTPException(400, f"{product.name}: bitta guruhdan bitta tanlanadi")

    consumption = [dict(l) for l in size["recipe"]]
    for mod in mods:
        consumption = apply_effect(consumption, mod.effect)
    unit_cost = sum(ings_by_key[l["ing"]].cost * l["qty"] for l in consumption if l["ing"] in ings_by_key)

    return {
        "key": "|".join([product.key, size["code"], *sorted(m.key for m in mods)]),
        "productId": product.key,
        "name": product.name,
        "size": size["label"],
        "modIds": [m.key for m in mods],
        "mods": [f"{m.name} sirop" if m.group == "syrup" else m.name for m in mods],
        "qty": qty,
        "unitPrice": size["price"] + sum(m.price for m in mods),
        "unitCost": round(unit_cost),
        "consumption": consumption,
    }


# ---------- promotions ----------

def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def promo_applies(promo, product_key: str, cat: str, at) -> bool:
    """`at` is a timezone-aware datetime in the café's local time."""
    if not promo.active:
        return False
    day = at.strftime("%Y-%m-%d")
    if promo.date_from and day < promo.date_from:
        return False
    if promo.date_to and day > promo.date_to:
        return False
    if promo.days and at.weekday() not in promo.days:
        return False
    start, end, now = _minutes(promo.start_time), _minutes(promo.end_time), at.hour * 60 + at.minute
    if start < end and not (start <= now < end):
        return False
    if start > end and not (now >= start or now < end):
        return False
    if promo.target == "category":
        return cat in promo.keys
    if promo.target == "product":
        return product_key in promo.keys
    return True


def round100(x: float) -> int:
    return int(math.floor(x / 100 + 0.5)) * 100


def apply_promotions(items: list[dict], cats: dict[str, str], promos: list, at) -> int:
    """Attach the best promotion to each item in place; return the total promo discount."""
    total = 0
    for it in items:
        best = None
        for p in promos:
            if promo_applies(p, it["productId"], cats.get(it["productId"], ""), at) and (best is None or p.pct > best.pct):
                best = p
        if best is None:
            it.pop("promo", None)
            it.pop("promoPct", None)
            it["promoDiscount"] = 0
            continue
        it["promo"] = best.name
        it["promoPct"] = best.pct
        it["promoDiscount"] = round100(it["unitPrice"] * it["qty"] * best.pct / 100)
        total += it["promoDiscount"]
    return total
