"""
Tests for the fingerprints module. Uses a fake session (no network).
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


class FingerprintsTests(unittest.TestCase):
    def _client(self, responses: List[_FakeResponse]) -> Tuple[Eveses, _FakeSession]:
        session = _FakeSession(responses)
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        return client, session

    def test_generate_returns_payload_and_price(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"fingerprint": {"id": "fp_1", "userAgent": {"value": "UA"}}, "price_micro_usd": 1600}),
        ])

        res = client.fingerprints.generate({"country": "US"})

        self.assertEqual(res.fingerprint["id"], "fp_1")
        self.assertEqual(res.price_micro_usd, 1600)

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://x.test/api/account/fingerprints/generate")
        self.assertEqual(json.loads(kwargs["data"]), {"country": "US"})

    def test_random_hits_random_endpoint(self) -> None:
        client, session = self._client([
            _FakeResponse(200, {"fingerprint": {"id": "fp_r"}}),
        ])

        res = client.fingerprints.random({"tags": "macOS"})

        self.assertEqual(res.fingerprint["id"], "fp_r")
        self.assertEqual(session.calls[0][1], "https://x.test/api/account/fingerprints/random")


if __name__ == "__main__":
    unittest.main()
