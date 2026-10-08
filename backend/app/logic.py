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
