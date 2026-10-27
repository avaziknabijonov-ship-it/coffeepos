"""Resolve combo ingredients once per unit; nested combos/modifiers are unsupported."""
from types import SimpleNamespace
from fastapi import HTTPException
from .logic import build_item


def resolve_combo(product, products, modifiers, ingredients):
    components = getattr(product, 'combo_components', None)
    if not components:
        return product
    consumption, snapshot = {}, []
    for component in components:
        child = products.get(component['productId'])
        if child is None or getattr(child, 'combo_components', None):
            raise HTTPException(409, 'Combo tarkibidagi mahsulot mavjud emas')
        built = build_item(child, component['size'], [], 1, modifiers, ingredients)
        for line in built['consumption']:
            if line['ing'] not in ingredients:
                raise HTTPException(409, 'Combo texkartasidagi xomashyo mavjud emas')
            consumption[line['ing']] = consumption.get(line['ing'], 0) + line['qty'] * component['qty']
        snapshot.append({'productId': child.key, 'name': child.name, 'size': component['size'],
                         'qty': component['qty'], 'unitPrice': built['unitPrice']})
    size = {**product.sizes[0], 'recipe': [{'ing': key, 'qty': quantity} for key, quantity in sorted(consumption.items())]}
    return SimpleNamespace(key=product.key, name=product.name, active=product.active,
                           sizes=[size], mods=[], combo_items=snapshot)
