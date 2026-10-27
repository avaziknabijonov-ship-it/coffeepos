"""Device revocation races need actual PostgreSQL row-lock behavior."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi.testclient import TestClient
from test_api import app
from test_devices import setup_company, sign_in, auth_header

pytestmark = pytest.mark.skipif(not os.environ.get('COFFEEPOS_TEST_POSTGRES_URL'),
                                reason='Requires isolated PostgreSQL CI service')


@pytest.mark.parametrize('scenario', ['double_revoke', 'relogin'])
def test_device_revocation_races(scenario):
    with TestClient(app) as c:
        owner, slug = setup_company(c)
        grant = c.post('/api/devices', headers=owner, json={'name': 'Concurrent tablet'}).json()
        did, secret = grant['device']['id'], grant['deviceSecret']
        previous = auth_header(sign_in(c, slug, secret=secret))
        barrier = Barrier(2)

        def send(index):
            barrier.wait(timeout=10)
            if scenario == 'relogin' and index == 1:
                return sign_in(c, slug, secret=secret)
            return c.post(f'/api/devices/{did}/revoke', headers=owner)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(send, range(2)))
        assert results[0].status_code == 200, results[0].text
        assert results[1].status_code in ((200,) if scenario == 'double_revoke' else (200, 403))
        if scenario == 'relogin' and results[1].status_code == 200:
            assert c.get('/api/me', headers=auth_header(results[1])).status_code == 401
        assert c.get('/api/me', headers=previous).status_code == 401
        events = c.get('/api/audit?action=device.revoke', headers=owner).json()['items']
        assert len(events) == 1
