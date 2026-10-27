"""Real row-lock tests. SQLite cannot validate PostgreSQL serialization."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_api import app
from test_refunds_api import company

pytestmark = pytest.mark.skipif(
    not os.environ.get("COFFEEPOS_TEST_POSTGRES_URL"), reason="Requires isolated PostgreSQL CI service"
)


@pytest.mark.parametrize("scenario", ["same_key", "over_refund", "cancel"])
def test_parallel_refund_serialization(scenario):
    with TestClient(app) as c:
        headers = company(c)
        assert c.post("/api/shifts/open", json={"openingCash": 0}, headers=headers).status_code == 200
        order = c.post("/api/orders", headers=headers, json={
            "items": [{"productId": "espresso", "size": "-", "qty": 1}], "payment": "karta",
        }).json()
        oid, total = order["id"], order["total"]
        body = {"clientKey": uuid4().hex, "amount": total, "method": "karta",
                "reason": "Concurrent refund", "externalConfirmed": True}
        barrier = Barrier(2)

        def send(index):
            barrier.wait(timeout=10)
            if scenario == "cancel" and index == 1:
                return c.post(f"/api/orders/{oid}/cancel", headers=headers,
                              json={"reason": "Concurrent cancel"})
            payload = {**body}
            if scenario == "over_refund" and index == 1:
                payload["clientKey"] = uuid4().hex
            return c.post(f"/api/orders/{oid}/refunds", headers=headers, json=payload)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(send, range(2)))
        statuses = sorted(r.status_code for r in results)
        if scenario == "same_key":
            assert statuses == [201, 201], [r.text for r in results]
            assert results[0].json()["id"] == results[1].json()["id"]
        elif scenario == "over_refund":
            assert statuses == [201, 422], [r.text for r in results]
        else:
            assert statuses in ([200, 409], [201, 409]), [r.text for r in results]
        refunds = c.get(f"/api/orders/{oid}/refunds", headers=headers).json()
        assert sum(r["amount"] for r in refunds) <= total
        assert len(refunds) <= 1
