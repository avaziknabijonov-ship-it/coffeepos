from fastapi.testclient import TestClient
from test_api import app, login
from test_refunds_api import company


def test_customer_consent_controls_reports_history_and_privacy():
    with TestClient(app) as c:
        h, other = company(c), company(c)
        assert c.put('/api/bonus/config', headers=h, json={
            'enabled': True, 'earn_percent': 5, 'redemption_limit_percent': 30,
        }).status_code == 200
        assert c.post('/api/shifts/open', headers=h, json={'openingCash': 0}).status_code == 200
        sale = {'items': [{'productId': 'espresso', 'size': '-', 'qty': 1}],
                'payment': 'karta', 'customerPhone': '+998901234567', 'customer': 'Customer'}
        orders = []
        for _ in range(2):
            response = c.post('/api/orders', headers=h, json=sale)
            assert response.status_code == 200, response.text
            orders.append(response.json())
        listed = c.get('/api/customers', headers=h)
        assert listed.status_code == 200, listed.text
        customer = listed.json()['items'][0]
        cid = customer['id']
        assert customer['phoneMasked'] == '***4567'
        assert '+998901234567' not in listed.text
        assert customer['analyticsConsent'] is False
        assert c.get('/api/reports/customers', headers=h).json()['orders'] == 0
        assert c.get(f'/api/customers/{cid}/purchases', headers=h).status_code == 403
        url = f'/api/customers/{cid}/analytics-consent'
        assert c.put(url, headers=h, json={'granted': True}).status_code == 422
        assert c.put(url, headers=other, json={'granted': True, 'operatorConfirmed': True}).status_code == 404
        assert c.put(url, headers=h, json={'granted': True, 'operatorConfirmed': True}).status_code == 200
        assert c.put(url, headers=h, json={'granted': True, 'operatorConfirmed': True}).status_code == 200
        audit = c.get('/api/audit?action=customer.analytics_consent', headers=h).json()
        assert len(audit['items']) == 1
        assert audit['items'][0]['after'] == {'analyticsConsent': True}
        report = c.get('/api/reports/customers?days=30', headers=h)
        assert report.status_code == 200, report.text
        data = report.json()
        assert data['consentingCustomers'] == data['purchasingCustomers'] == data['repeatCustomers'] == 1
        assert data['orders'] == 2
        assert data['revenue'] == sum(o['total'] for o in orders)
        assert data['cohorts'][0]['customers'] == 1 and data['cohorts'][0]['orders'] == 2
        assert 'Customer' not in report.text.replace('consentingCustomers', '').replace('purchasingCustomers', '').replace('repeatCustomers', '')
        assert '+998901234567' not in report.text
        assert len(c.get(f'/api/customers/{cid}/purchases', headers=h).json()['items']) == 2
        assert c.get(f'/api/customers/{cid}/purchases', headers=other).status_code == 404
        assert c.get('/api/reports/customers', headers=other).json()['orders'] == 0
        assert c.get('/api/reports/customers').status_code == 401
        assert c.get('/api/reports/customers', headers=login(c, '2222')).status_code == 403
        assert c.get('/api/reports/customers?days=93', headers=h).status_code == 422
        assert c.get('/api/customers?limit=101', headers=h).status_code == 422
        assert c.put(url, headers=h, json={'granted': False}).status_code == 200
        assert c.get('/api/reports/customers', headers=h).json()['orders'] == 0
        assert c.get(f'/api/customers/{cid}/purchases', headers=h).status_code == 403


def test_additive_customer_consent_migration_preserves_old_data(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, text, inspect
    from app.db import Base
    import app.main as main

    # Dedicated temporary DB only: reproduce a pre-consent customers table.
    engine = create_engine('sqlite:///' + str(tmp_path / 'legacy.db'))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for column in ('analytics_consent', 'consent_updated_at', 'consent_actor_id'):
            conn.execute(text('ALTER TABLE customers DROP COLUMN ' + column))
        conn.execute(text("INSERT INTO customers (id,company_id,phone,name,bonus_balance,created_at) VALUES (1,1,'998901234567','Legacy',123,1)"))
    monkeypatch.setattr(main, 'engine', engine)
    main.migrate()
    main.migrate()  # Re-running the migration must not destroy or duplicate data.
    assert {'analytics_consent', 'consent_updated_at', 'consent_actor_id'} <= {c['name'] for c in inspect(engine).get_columns('customers')}
    with engine.connect() as conn:
        row = conn.execute(text('SELECT name,bonus_balance,analytics_consent,consent_updated_at FROM customers')).one()
        assert tuple(row) == ('Legacy', 123, 0, None)
    engine.dispose()
