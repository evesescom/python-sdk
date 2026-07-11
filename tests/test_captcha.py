"""
Tests for the captcha module. Uses a fake session (no network); canned
responses use retry_after=0 so the blocking poll never actually sleeps.
"""

from __future__ import annotations

import json
import unittest
from typing import Any, Dict, List, Optional, Tuple

from eveses import Eveses, EvesesError


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


class CaptchaTests(unittest.TestCase):
    def _client(self, responses: List[_FakeResponse]) -> Tuple[Eveses, _FakeSession]:
        session = _FakeSession(responses)
        client = Eveses(api_key="k", base_url="https://x.test", session=session)
        return client, session

    def test_solve_polls_until_ready(self) -> None:
        client, session = self._client([
            _FakeResponse(201, {"task_id": 7, "status": "queued", "price_micro_usd": 3392, "retry_after": 0}),
            _FakeResponse(200, {"status": "processing", "retry_after": 0}),
            _FakeResponse(200, {"status": "ready", "solution": "TOK", "retry_after": 0}),
        ])

        res = client.captcha.solve("RecaptchaV2TaskProxyless", {"websiteURL": "x", "websiteKey": "k"})

        self.assertEqual(res.task_id, 7)
        self.assertEqual(res.status, "ready")
        self.assertEqual(res.solution, "TOK")
        self.assertEqual(res.price_micro_usd, 3392)

        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://x.test/api/account/captcha/solve")
        sent = json.loads(kwargs["data"])
        self.assertEqual(sent, {"type": "RecaptchaV2TaskProxyless", "params": {"websiteURL": "x", "websiteKey": "k"}})
        self.assertEqual(session.calls[1][1], "https://x.test/api/account/captcha/result/7")

    def test_solve_raises_on_failure(self) -> None:
        client, _ = self._client([
            _FakeResponse(201, {"task_id": 9, "status": "queued", "retry_after": 0}),
            _FakeResponse(200, {"status": "failed", "error": "ERROR_CAPTCHA_UNSOLVABLE", "retry_after": 0}),
        ])
        with self.assertRaises(EvesesError) as ctx:
            client.captcha.solve("ImageToTextTask", {})
        self.assertIn("ERROR_CAPTCHA_UNSOLVABLE", str(ctx.exception))

    def test_solve_sends_idempotency_key(self) -> None:
        client, session = self._client([
            _FakeResponse(201, {"task_id": 3, "status": "ready", "solution": "A", "retry_after": 0}),
        ])
        res = client.captcha.solve("ImageToTextTask", {}, idempotency_key="idem-c")
        self.assertEqual(res.solution, "A")
        self.assertEqual(session.calls[0][2]["headers"]["Idempotency-Key"], "idem-c")


if __name__ == "__main__":
    unittest.main()
