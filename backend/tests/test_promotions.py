from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from app.promotions import is_active, choose_promotion, discount_amount
from test_api import app, login
from test_refunds_api import company

TZ = ZoneInfo('Asia/Tashkent')


def rule(**changes):
    return SimpleNamespace(**({'id': 1, 'active': True, 'start_time': '22:00',
        'end_time': '02:00', 'weekdays': [0], 'priority': 0, 'percent': 20} | changes))


def test_schedule_overnight_priority_and_caps():
    assert is_active(rule(), datetime(2026, 10, 26, 22, tzinfo=TZ))
    assert is_active(rule(), datetime(2026, 10, 27, 1, 59, tzinfo=TZ))
    assert not is_active(rule(), datetime(2026, 10, 27, 2, tzinfo=TZ))
    assert not is_active(rule(), datetime(2026, 10, 26, 1, tzinfo=TZ))
    assert not is_active(rule(active=False), datetime(2026, 10, 26, 22, tzinfo=TZ))
    now = datetime(2026, 10, 26, 23, tzinfo=TZ)
    assert choose_promotion([rule(id=3), rule(id=2, priority=10), rule(id=1, priority=10)], now).id == 1
    for subtotal in (1, 99, 101, 555, 12500, 30000, 999999):
        for percent in (0, 1, 17, 50):
            value = discount_amount(subtotal, percent)
            assert type(value) is int and 0 <= value <= subtotal * percent // 100
    assert discount_amount(30000, 20) == 6000


def test_promotion_checkout_snapshot_and_security(monkeypatch):
    import app.main as main
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed = datetime(2026, 10, 26, 15, tzinfo=TZ)
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
    monkeypatch.setattr(main, 'datetime', Clock)
    with TestClient(app) as c:
        h, other = company(c), company(c)
        payload = {'name': 'Afternoon', 'startTime': '14:00', 'endTime': '17:00',
                   'weekdays': [0], 'percent': 20, 'priority': 10, 'active': True}
        response = c.post('/api/promotions', headers=h, json=payload)
        assert response.status_code == 201, response.text
        promotion = response.json()
        assert c.get('/api/promotions', headers=other).json() == []
        assert c.get('/api/promotions/active', headers=h).json()['promotion']['id'] == promotion['id']
        assert c.put(f"/api/promotions/{promotion['id']}", headers=other, json=payload).status_code == 404
        assert c.post('/api/promotions', headers=login(c, '2222'), json=payload).status_code == 403
        for invalid in ({'percent': 51}, {'weekdays': [0, 0]}, {'weekdays': [7]},
                        {'endTime': '14:00'}, {'startTime': '25:00'}, {'name': '   '}):
            assert c.post('/api/promotions', headers=h, json=payload | invalid).status_code == 422
        assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
        sale = {'items': [{'productId': 'latte', 'size': 'M', 'qty': 1}], 'payment': 'karta'}
        assert c.post('/api/orders', headers=h, json=sale).status_code == 409  # Legacy client must update.
        assert c.post('/api/orders', headers=h, json=sale | {'expectedTotal': 30000}).status_code == 409
        saved = c.post('/api/orders', headers=h, json=sale | {'expectedTotal': 24000})
        assert saved.status_code == 200, saved.text
        order = saved.json()
        assert order['discount'] == 6000 and order['total'] == 24000
        assert order['promotion']['name'] == 'Afternoon'
        manual = c.post('/api/orders', headers=h, json=sale | {'discountPct': 30, 'expectedTotal': 21000})
        assert manual.status_code == 200, manual.text
        assert manual.json()['promotion'] is None and manual.json()['discount'] == 9000
        assert c.put(f"/api/promotions/{promotion['id']}", headers=h, json=payload | {'active': False}).status_code == 200
        assert c.get('/api/promotions/active', headers=h).json()['promotion'] is None
        historical = c.get('/api/orders/history', headers=h, params={
            'from_ms': order['createdAt'] - 1, 'to_ms': order['createdAt'] + 86400000,
        }).json()
        snapshot = next(o for o in historical if o['id'] == order['id'])
        assert snapshot['promotion'] == order['promotion'] and snapshot['total'] == 24000
