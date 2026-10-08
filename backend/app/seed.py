"""Default coffee-bar menu template copied into every new company."""

UNITS = ("g", "ml", "dona")

INGREDIENTS = [
    ("beans", "Kofe doni (arabika)", "g", 260, 4200, 1000),
    ("milk", "Sut 3,2%", "ml", 14, 18000, 5000),
    ("almond", "Bodom suti", "ml", 48, 2500, 1000),
    ("coconut", "Kokos suti", "ml", 46, 1800, 1000),
    ("lactfree", "Laktozasiz sut", "ml", 22, 3000, 1000),
    ("cream", "Qaymoq 10%", "ml", 30, 2000, 500),
    ("syr-caramel", "Karamel sirop", "ml", 170, 1400, 300),
    ("syr-vanilla", "Vanil sirop", "ml", 170, 1200, 300),
    ("syr-hazelnut", "Findiq sirop", "ml", 170, 1100, 300),
    ("choc", "Shokolad sousi", "ml", 120, 900, 300),
    ("matcha", "Matcha kukuni", "g", 900, 300, 100),
    ("tea-black", "Qora choy (paket)", "dona", 900, 120, 30),
    ("tea-green", "Ko'k choy (paket)", "dona", 900, 100, 30),
    ("ice", "Muz", "g", 2, 10000, 2000),
    ("cup-s", "Stakan S (250 ml)", "dona", 650, 400, 100),
    ("cup-m", "Stakan M (350 ml)", "dona", 750, 350, 100),
    ("cup-l", "Stakan L (450 ml)", "dona", 850, 300, 100),
    ("cup-cold", "Sovuq ichimlik stakani", "dona", 900, 300, 100),
    ("lid", "Qopqoq", "dona", 300, 900, 200),
    ("straw", "Trubochka", "dona", 100, 800, 200),
    ("croissant", "Kruassan", "dona", 9000, 18, 5),
    ("cheesecake", "Chizkeyk (bo'lak)", "dona", 15000, 10, 4),
    ("brownie", "Brauni", "dona", 8000, 14, 5),
]

CATEGORIES = [
    ("espresso", "Espresso"),
    ("milk", "Sutli kofe"),
    ("cold", "Sovuq"),
    ("tea", "Choy"),
    ("dessert", "Desert"),
]


def _l(ing, qty):
    return {"ing": ing, "qty": qty}


def _hot(cup, *lines):
    return [*lines, _l(cup, 1), _l("lid", 1)]


def _cold(*lines):
    return [*lines, _l("cup-cold", 1), _l("straw", 1)]


def _size(code, volume, price, recipe):
    return {"code": code, "label": code, "volume": volume, "price": price, "recipe": recipe}


def S(price, recipe):
    return _size("S", "250 ml", price, recipe)


def M(price, recipe):
    return _size("M", "350 ml", price, recipe)


def L(price, recipe):
    return _size("L", "450 ml", price, recipe)


def one(price, recipe):
    return {"code": "-", "label": "", "price": price, "recipe": recipe}


PRODUCTS = [
    ("espresso", "espresso", "Espresso", [], [one(15000, [_l("beans", 9)])]),
    ("doppio", "espresso", "Doppio", [], [one(20000, [_l("beans", 18)])]),
    ("americano", "espresso", "Amerikano", ["syrup", "shot"], [
        S(18000, _hot("cup-s", _l("beans", 9))), M(22000, _hot("cup-m", _l("beans", 18))), L(26000, _hot("cup-l", _l("beans", 18)))]),
    ("cappuccino", "milk", "Kapuchino", ["milk", "syrup", "shot"], [
        S(24000, _hot("cup-s", _l("beans", 9), _l("milk", 150))), M(28000, _hot("cup-m", _l("beans", 18), _l("milk", 200))),
        L(32000, _hot("cup-l", _l("beans", 18), _l("milk", 280)))]),
    ("latte", "milk", "Latte", ["milk", "syrup", "shot"], [
        S(26000, _hot("cup-s", _l("beans", 9), _l("milk", 180))), M(30000, _hot("cup-m", _l("beans", 18), _l("milk", 240))),
        L(34000, _hot("cup-l", _l("beans", 18), _l("milk", 320)))]),
    ("flatwhite", "milk", "Flat uayt", ["milk", "syrup"], [S(30000, _hot("cup-s", _l("beans", 18), _l("milk", 150)))]),
    ("raf", "milk", "Raf", ["syrup", "shot"], [
        M(34000, _hot("cup-m", _l("beans", 18), _l("cream", 200), _l("syr-vanilla", 10))),
        L(38000, _hot("cup-l", _l("beans", 18), _l("cream", 280), _l("syr-vanilla", 15)))]),
    ("mocha", "milk", "Mokko", ["milk", "syrup", "shot"], [
        S(28000, _hot("cup-s", _l("beans", 9), _l("milk", 130), _l("choc", 20))),
        M(32000, _hot("cup-m", _l("beans", 18), _l("milk", 180), _l("choc", 25))),
        L(36000, _hot("cup-l", _l("beans", 18), _l("milk", 250), _l("choc", 30)))]),
    ("icelatte", "cold", "Ays latte", ["milk", "syrup", "shot"], [
        M(32000, _cold(_l("beans", 18), _l("milk", 200), _l("ice", 150))), L(36000, _cold(_l("beans", 18), _l("milk", 280), _l("ice", 180)))]),
    ("iceamericano", "cold", "Ays amerikano", ["syrup", "shot"], [
        M(24000, _cold(_l("beans", 18), _l("ice", 200))), L(28000, _cold(_l("beans", 18), _l("ice", 250)))]),
    ("frappe", "cold", "Frappe karamel", ["milk", "syrup"], [
        one(38000, _cold(_l("beans", 18), _l("milk", 150), _l("ice", 200), _l("cream", 30), _l("syr-caramel", 20)))]),
    ("blacktea", "tea", "Qora choy", [], [S(12000, _hot("cup-s", _l("tea-black", 1))), L(15000, _hot("cup-l", _l("tea-black", 2)))]),
    ("greentea", "tea", "Ko'k choy", [], [S(12000, _hot("cup-s", _l("tea-green", 1))), L(15000, _hot("cup-l", _l("tea-green", 2)))]),
    ("matcha", "tea", "Matcha latte", ["milk", "syrup"], [
        M(34000, _hot("cup-m", _l("matcha", 4), _l("milk", 240))), L(38000, _hot("cup-l", _l("matcha", 6), _l("milk", 320)))]),
    ("croissant", "dessert", "Kruassan", [], [one(20000, [_l("croissant", 1)])]),
    ("cheesecake", "dessert", "Chizkeyk", [], [one(32000, [_l("cheesecake", 1)])]),
    ("brownie", "dessert", "Brauni", [], [one(22000, [_l("brownie", 1)])]),
]

DEFAULT_MILK = "milk-regular"

MODIFIERS = [
    (DEFAULT_MILK, "milk", "Oddiy sut", 0, {"type": "none"}),
    ("milk-almond", "milk", "Bodom suti", 6000, {"type": "swap", "from": "milk", "to": "almond"}),
    ("milk-coconut", "milk", "Kokos suti", 6000, {"type": "swap", "from": "milk", "to": "coconut"}),
    ("milk-lactfree", "milk", "Laktozasiz", 4000, {"type": "swap", "from": "milk", "to": "lactfree"}),
    ("syr-caramel", "syrup", "Karamel", 4000, {"type": "add", "ing": "syr-caramel", "qty": 15}),
    ("syr-vanilla", "syrup", "Vanil", 4000, {"type": "add", "ing": "syr-vanilla", "qty": 15}),
    ("syr-hazelnut", "syrup", "Findiq", 4000, {"type": "add", "ing": "syr-hazelnut", "qty": 15}),
    ("shot1", "shot", "+1 shot", 5000, {"type": "add", "ing": "beans", "qty": 9}),
    ("shot2", "shot", "+2 shot", 10000, {"type": "add", "ing": "beans", "qty": 18}),
]
