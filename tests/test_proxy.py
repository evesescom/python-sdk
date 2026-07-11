"""
Tests for the proxy module. Uses a fake session (no network); asserts
method / url / body / headers on the wire.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Dict, List, Optional, Tuple

from eveses import Eveses


class _FakeResponse:
    def __init__(self, status_code: int, body: Any = None, headers: Optional[Dict[str, str]] = None) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.reason = "OK" if 200 <= status_code < 300 else "Error"
        self.text = "" if body is None else json.dumps(body)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no body")
        return self._body


class _FakeSession:
    def __init__(self, responses: List[_FakeResponse]) -> None:
        self._queue = list(responses)
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append((method, url, kwargs))
        if not self._queue:
            raise AssertionError("FakeSession: no more responses queued")
        return self._queue.pop(0)


class ProxyTests(unittest.TestCase):
    def _client(self, responses: List[_FakeResponse]) -> Tuple[Eveses, _FakeSession]:
        session = _FakeSession(responses)
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        return client, session

    def test_purchase_residential_sends_body_and_idempotency_key(self) -> None:
        client, session = self._client([
            _FakeResponse(201, {
                "uuid": "px_abc", "type": "residential", "kind": "metered", "gb": 10,
                "status": "active", "price_cents": 900, "auto_extend": False, "extendable": False,
            }),
        ])
        order = client.proxy.purchase(type="residential", gb=10, subscription=True, idempotency_key="idem-px")

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://x.test/api/account/proxies/purchase")
        self.assertEqual(kwargs["headers"]["Idempotency-Key"], "idem-px")
        self.assertEqual(json.loads(kwargs["data"]), {"type": "residential", "gb": 10, "subscription": True})

        self.assertEqual(order.uuid, "px_abc")
        self.assertEqual(order.status, "active")
        self.assertEqual(order.price_cents, 900)
        self.assertEqual(order.currency, "USD")
        self.assertEqual(order.gb, 10.0)

    def test_purchase_static_sends_selection(self) -> None:
        client, session = self._client([
            _FakeResponse(201, {"uuid": "px_isp", "type": "isp", "status": "active", "price_cents": 300}),
        ])
        client.proxy.purchase(
            type="isp", product_id=9, plan_id=4, location_id=51, location_name="Australia", quantity=3,
        )
        sent = json.loads(session.calls[0][2]["data"])
        self.assertEqual(sent, {
            "type": "isp", "product_id": 9, "plan_id": 4, "location_id": 51,
            "location_name": "Australia", "quantity": 3,
        })

    def test_quote_residential_builds_params(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"price_cents": 900, "gb": 10, "currency": "USD"}),
        ])
        quote = client.proxy.quote(type="residential", gb=10, subscription=True)

        method, url, kwargs = session.calls[0]
        self.assertEqual(url, "https://x.test/api/account/proxies/quote")
        self.assertEqual(kwargs["params"], {"type": "residential", "gb": 10, "subscription": "true"})
        self.assertEqual(quote["price_cents"], 900)

    def test_list_maps_residential_subscription_and_orders(self) -> None:
        client, _ = self._client([
            _FakeResponse(200, {
                "residential": {"host": "proxy.eveses.com", "username": "u", "password": "p", "traffic_gb_available": 5, "traffic_gb_used": 1},
                "subscription": {"status": "active", "gb": 10, "discount_pct": 15, "renew_failures": 0},
                "orders": [{"uuid": "px_1", "type": "isp", "status": "active", "price_cents": 300}],
            }),
        ])
        result = client.proxy.list()

        self.assertEqual(result.residential["username"], "u")
        self.assertEqual(result.subscription.status, "active")
        self.assertEqual(result.subscription.discount_pct, 15)
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.orders[0].uuid, "px_1")

    def test_extend_and_auto_renew_hit_order_routes(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"uuid": "px_1", "type": "isp", "status": "active", "price_cents": 300}),
            _FakeResponse(200, {"uuid": "px_1", "type": "isp", "status": "active", "price_cents": 300, "auto_extend": True}),
        ])

        client.proxy.extend("px_1", 30)
        self.assertEqual(session.calls[0][1], "https://x.test/api/account/proxies/px_1/extend")
        self.assertEqual(json.loads(session.calls[0][2]["data"]), {"days": 30})

        order = client.proxy.auto_renew("px_1", True)
        self.assertEqual(session.calls[1][1], "https://x.test/api/account/proxies/px_1/auto-renew")
        self.assertEqual(json.loads(session.calls[1][2]["data"]), {"enabled": True})
        self.assertTrue(order.auto_extend)

    def test_subscription_pause_posts_to_route(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"status": "paused", "gb": 10, "discount_pct": 15}),
        ])
        sub = client.proxy.subscription_pause()
        self.assertEqual(session.calls[0][0], "POST")
        self.assertEqual(session.calls[0][1], "https://x.test/api/account/proxies/subscription/pause")
        self.assertEqual(sub.status, "paused")


if __name__ == "__main__":
    unittest.main()
