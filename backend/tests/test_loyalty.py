from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.db import LoyaltyCustomer, SessionLocal
from app.main import app


def setup(c):
    slug = 'bonus-' + uuid4().hex[:12]
    r = c.post('/api/auth/register', json={'companyName': 'Bonus cafe', 'slug': slug, 'ownerName': 'Owner', 'ownerPin': '1234'})
    assert r.status_code == 200, r.text
    h = {'Authorization': 'Bearer ' + r.json()['token']}
    assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
    return h


def sale(c, h, **fields):
    return c.post('/api/orders', headers=h, json={'items': [{'productId': 'latte', 'size': 'M', 'qty': 1}], 'payment': 'karta', **fields})


def test_loyalty_earn_spend_limits_and_tenant_isolation():
    with TestClient(app) as c:
        h = setup(c)
        other = setup(c)
        assert c.get('/api/loyalty/config', headers=h).json()['enabled'] is False
        customer = c.post('/api/loyalty/customers', headers=h, json={'phone': '90 123 45 67', 'name': 'Ali'}).json()
        cid = customer['id']
        assert c.post('/api/loyalty/customers', headers=h, json={'phone': '+998(90)123-45-67'}).json()['id'] == cid
        assert sale(c, h, loyaltyCustomerId=cid).status_code == 400
        cfg = {'enabled': True, 'earnPct': 5, 'redeemPct': 30}
        assert c.put('/api/loyalty/config', headers=h, json=cfg).status_code == 200
        first = sale(c, h, loyaltyCustomerId=cid).json()
        assert first['total'] == 30000
        assert first['bonusEarned'] == 1500 and first['bonusBalance'] == 1500
        assert sale(c, h, loyaltyCustomerId=cid, bonusSpend=1501).status_code == 409
        assert sale(c, h, bonusSpend=1).status_code == 400
        assert sale(c, h, loyaltyCustomerId=cid, bonusSpend=-1).status_code == 422
        assert sale(c, h, loyaltyCustomerId=cid, bonusSpend=1.5).status_code == 422
        assert sale(c, h, loyaltyCustomerId=cid, payment='qarz', customer='Ali').status_code == 400
        assert sale(c, h, loyaltyCustomerId=cid, bonusSpend=1000, payment='naqd', cashGiven=1000).status_code == 400
        second = sale(c, h, loyaltyCustomerId=cid, bonusSpend=1000, discountPct=10, payment='naqd', cashGiven=26000).json()
        assert second['discount'] == 3000 and second['total'] == 26000
        assert second['bonusEarned'] == 1300 and second['bonusBalance'] == 1800
        assert second['bonusUsed'] == 1000
        history = c.get(f'/api/loyalty/customers/{cid}/history', headers=h).json()
        assert len(history) == 2 and history[0]['balance'] == 1800
        # Customer IDs, phone lookups, settings and ledgers are tenant scoped.
        assert c.get('/api/loyalty/customers?phone=901234567', headers=other).json()['customer'] is None
        assert c.get(f'/api/loyalty/customers/{cid}/history', headers=other).status_code == 404
        assert c.get('/api/loyalty/config', headers=other).json()['enabled'] is False
        c.put('/api/loyalty/config', headers=other, json=cfg)
        assert sale(c, other, loyaltyCustomerId=cid).status_code == 404
        # Cap uses discounted total; balance cannot bypass it.
        with SessionLocal() as db:
            db.execute(update(LoyaltyCustomer).where(LoyaltyCustomer.id == cid).values(balance=50000))
            db.commit()
        assert sale(c, h, loyaltyCustomerId=cid, bonusSpend=9001).status_code == 400
        assert sale(c, h, loyaltyCustomerId=cid, bonusSpend=9000, discountPct=50).status_code == 400
        assert c.post('/api/loyalty/customers', headers=h, json={'phone': '123'}).status_code == 400
        assert c.post('/api/loyalty/customers', headers=h, json={'phone': 'letters901234567'}).status_code == 400


def test_loyalty_roles_and_simultaneous_redemption():
    with TestClient(app) as c:
        h = setup(c)
        cfg = {'enabled': True, 'earnPct': 0, 'redeemPct': 100}
        c.put('/api/loyalty/config', headers=h, json=cfg)
        me = c.get('/api/me', headers=h).json()
        for name, role, pin in [('Cashier', 'kassir', '5678'), ('Barista', 'barista', '6789')]:
            assert c.post('/api/staff', headers=h, json={'name': name, 'role': role, 'pin': pin}).status_code == 200
        def login(pin):
            r = c.post('/api/auth/login', json={'company': me['company']['slug'], 'pin': pin})
            return {'Authorization': 'Bearer ' + r.json()['token']}
        cashier, barista = login('5678'), login('6789')
        assert c.put('/api/loyalty/config', headers=cashier, json=cfg).status_code == 403
        assert c.get('/api/loyalty/customers?phone=901234567', headers=barista).status_code == 403
        customer = c.post('/api/loyalty/customers', headers=cashier, json={'phone': '901234567'}).json()
        cid = customer['id']
        with SessionLocal() as db:
            db.execute(update(LoyaltyCustomer).where(LoyaltyCustomer.id == cid).values(balance=1000))
            db.commit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: sale(c, cashier, loyaltyCustomerId=cid, bonusSpend=1000).status_code, range(2)))
        assert sorted(results) == [200, 409]
        with SessionLocal() as db:
            assert db.scalar(select(LoyaltyCustomer.balance).where(LoyaltyCustomer.id == cid)) == 0
        assert len(c.get(f'/api/loyalty/customers/{cid}/history', headers=h).json()) == 1


def test_loyalty_migration_preserves_existing_orders(tmp_path):
    import os
    import subprocess
    import sys
    script = '''
from sqlalchemy import text
from app.main import init_db
from app.db import engine, SessionLocal, Company, Shift, Order
from sqlalchemy import select
init_db()
with SessionLocal() as db:
    company = db.scalar(select(Company))
    shift = Shift(company_id=company.id, staff_name='Owner', opening_cash=0)
    db.add(shift)
    db.flush()
    db.add(Order(company_id=company.id, shift_id=shift.id, number=1, customer='Old customer', items=[], subtotal=30000, discount=0, total=30000, cost=5000, payment='karta', staff_name='Owner'))
    db.commit()
with engine.begin() as conn:
    for column in ('bonus_used', 'bonus_earned', 'bonus_balance'):
        conn.execute(text('ALTER TABLE orders DROP COLUMN ' + column))
init_db()
init_db()
with engine.connect() as conn:
    assert conn.execute(text('SELECT count(*) FROM companies')).scalar() == 1
    assert conn.execute(text('SELECT total, bonus_used, bonus_earned, bonus_balance FROM orders')).all() == [(30000, 0, 0, None)]
'''
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{tmp_path}/legacy.db'}
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_admin_bonus_adjustments_are_audited_scoped_and_repeat_safe():
    with TestClient(app) as c:
        h, other = setup(c), setup(c)
        customer = c.post('/api/loyalty/customers', headers=h, json={'phone': '901112233', 'name': 'Bonus client'}).json()
        cid = customer['id']
        url = f'/api/loyalty/customers/{cid}/adjustments'
        body = {'amount': 1000, 'reason': 'Opening promotion', 'requestId': uuid4().hex}
        r = c.post(url, headers=h, json=body)
        assert r.status_code == 200, r.text
        assert r.json()['customer']['balance'] == 1000
        assert c.post(url, headers=h, json=body).json()['customer']['balance'] == 1000
        assert c.post(url, headers=h, json={**body, 'amount': 2000}).status_code == 409
        assert c.post(url, headers=other, json={**body, 'requestId': uuid4().hex}).status_code == 404
        for delta, reason, expected in [(0, 'zero', 400), (1, '   ', 400), (1.5, 'fraction', 422), (-1001, 'too much', 409), (1000000001, 'too large', 422)]:
            assert c.post(url, headers=h, json={'amount': delta, 'reason': reason, 'requestId': uuid4().hex}).status_code == expected
        minus = {'amount': -300, 'reason': 'Correction', 'requestId': uuid4().hex}
        assert c.post(url, headers=h, json=minus).json()['customer']['balance'] == 700
        assert c.post(url, headers=h, json=minus).json()['customer']['balance'] == 700
        history = c.get(f'/api/loyalty/customers/{cid}/history', headers=h).json()
        assert len(history) == 2
        assert {x['reason'] for x in history} == {'Opening promotion', 'Correction'}
        assert all(x['staff'] == 'Owner' and x['kind'] == 'adjustment' and x['orderId'] is None for x in history)
        assert c.post('/api/staff', headers=h, json={'name': 'Cashier', 'role': 'kassir', 'pin': '5678'}).status_code == 200
        slug = c.get('/api/me', headers=h).json()['company']['slug']
        token = c.post('/api/auth/login', json={'company': slug, 'pin': '5678'}).json()['token']
        assert c.post(url, headers={'Authorization': 'Bearer ' + token}, json={**body, 'requestId': uuid4().hex}).status_code == 403
        # Identical simultaneous retries credit the account only once.
        concurrent = {'amount': 100, 'reason': 'Retry test', 'requestId': uuid4().hex}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: c.post(url, headers=h, json=concurrent), range(2)))
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        current = c.get('/api/loyalty/customers?phone=901112233', headers=h).json()['customer']
        assert current['balance'] == 800
        assert len(c.get(f'/api/loyalty/customers/{cid}/history', headers=h).json()) == 3
        # Repeating a previous debit after a later operation does not debit again.
        assert c.post(url, headers=h, json=minus).json()['customer']['balance'] == 800
