"""
Tests for client.numbers.* — the merged orders + catalog surface.

Same fake-session style as test_client.py; never touches the network.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Dict, List, Optional, Tuple

from eveses import Eveses


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
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


class NumbersOrdersTests(unittest.TestCase):
    def test_actions_hit_v1_numbers_routes(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"order_id": "X", "status": "canceled"}}),
            _FakeResponse(200, {"data": {"order_id": "X", "status": "completed"}}),
            _FakeResponse(200, {"data": {"order_id": "X", "status": "waiting_sms"}}),
            _FakeResponse(200, {"data": {"order_id": "X", "status": "waiting_sms"}}),
        ])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)

        client.numbers.cancel("X")
        client.numbers.finish("X")
        client.numbers.retry("X")
        client.numbers.auto_renew("X", True)

        urls = [c[1] for c in session.calls]
        self.assertEqual(urls[0], "https://x.test/api/v1/numbers/orders/X/cancel")
        self.assertEqual(urls[1], "https://x.test/api/v1/numbers/orders/X/finish")
        self.assertEqual(urls[2], "https://x.test/api/v1/numbers/orders/X/retry")
        self.assertEqual(urls[3], "https://x.test/api/v1/numbers/orders/X/auto-renew")

    def test_batch_posts_orders_list(self) -> None:
        session = _FakeSession([_FakeResponse(200, {"data": []})])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        client.numbers.batch([{"country": "ua", "service": "telegram"}])
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://x.test/api/v1/numbers/orders/batch")
        self.assertEqual(
            json.loads(kwargs["data"]),
            {"orders": [{"country": "ua", "service": "telegram"}]},
        )


class NumbersCatalogTests(unittest.TestCase):
    def test_countries_default_mode(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"mode": "activation", "countries": ["ua", "pl", "de"]}})
        ])
        client = Eveses(api_key="k", base_url="https://api.example.test", session=session)
        res = client.numbers.countries()

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example.test/api/v1/numbers/countries")
        self.assertEqual(kwargs["params"], {"mode": "activation"})
        self.assertEqual(res.countries, ["ua", "pl", "de"])

    def test_services_alias_returns_product_list(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": {"mode": "activation", "products": ["telegram", "wa"]}})
        ])
        client = Eveses(api_key="k", base_url="https://api.example.test", session=session)
        res = client.numbers.services(mode="activation", country="UA", currency="usd")

        method, url, kwargs = session.calls[0]
        self.assertEqual(url, "https://api.example.test/api/v1/numbers/products")
        self.assertEqual(res.services, ["telegram", "wa"])
        self.assertEqual(res.country, "ua")
        self.assertEqual(res.currency, "USD")

    def test_pricing_validates_required_args(self) -> None:
        session = _FakeSession([])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        with self.assertRaises(ValueError):
            client.numbers.pricing(country="", service="telegram")
        with self.assertRaises(ValueError):
            client.numbers.pricing(country="ua", service="")

    def test_pricing_maps_services_and_durations(self) -> None:
        session = _FakeSession([
            _FakeResponse(
                200,
                {
                    "data": {
                        "mode": "activation",
                        "country": "ua",
                        "currency": "USD",
                        "services": [
                            {
                                "name": "telegram",
                                "durations": [
                                    {
                                        "duration_minutes": 0,
                                        "price_cents": 50,
                                        "price": 0.5,
                                        "currency": "USD",
                                        "in_stock": True,
                                    }
                                ],
                            }
                        ],
                    }
                },
            )
        ])
        client = Eveses(api_key="k", base_url="https://api.example.test", session=session)
        res = client.numbers.pricing(
            mode="activation",
            country="UA",
            service="telegram",
            currency="usd",
        )

        params = session.calls[0][2]["params"]
        self.assertEqual(params["mode"], "activation")
        self.assertEqual(params["country"], "ua")
        self.assertEqual(params["product"], "telegram")
        self.assertEqual(params["currency"], "USD")

        self.assertEqual(len(res.services), 1)
        self.assertEqual(res.services[0].name, "telegram")
        self.assertEqual(res.services[0].durations[0].price_cents, 50)
        self.assertEqual(res.services[0].durations[0].available, True)


class AggregateTests(unittest.TestCase):
    def test_orders_pricing_quotas_captcha_usage_hit_v1(self) -> None:
        session = _FakeSession([
            _FakeResponse(200, {"data": [], "meta": {}}),
            _FakeResponse(200, {"currency": "USD"}),
            _FakeResponse(200, {"proxy": []}),
            _FakeResponse(200, {"data": [], "meta": {}}),
            _FakeResponse(200, {"abilities": ["*"], "features": {"proxy": True}}),
        ])
        client = Eveses(api_key="k", base_url="https://x.test", session=session)

        client.orders.list(service="proxy")
        client.pricing.all()
        client.quotas.all()
        client.captcha.usage(status="ready")
        me = client.me.get()

        urls = [c[1] for c in session.calls]
        self.assertEqual(urls[0], "https://x.test/api/v1/orders")
        self.assertEqual(urls[1], "https://x.test/api/v1/pricing")
        self.assertEqual(urls[2], "https://x.test/api/v1/quotas")
        self.assertEqual(urls[3], "https://x.test/api/v1/captcha/usage")
        self.assertEqual(urls[4], "https://x.test/api/v1/me")
        self.assertEqual(me.abilities, ["*"])
        self.assertEqual(me.features, {"proxy": True})


if __name__ == "__main__":
    unittest.main()
