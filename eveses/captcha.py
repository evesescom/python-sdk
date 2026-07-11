"""
Captcha-solving namespace. Resells 2captcha, billed pay-per-use from the wallet
(count-on-success). Hits `/api/account/captcha/*`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from .exceptions import EvesesError

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses

_DEFAULT_TIMEOUT_SEC = 180


@dataclass
class CaptchaSolution:
    task_id: int
    status: str
    solution: Optional[str] = None
    error: Optional[str] = None
    price_micro_usd: Optional[int] = None


class Captcha:
    def __init__(self, client: "Eveses", sleeper: Optional[Callable[[int], None]] = None) -> None:
        self._client = client
        self._sleep = sleeper or (lambda s: time.sleep(s) if s > 0 else None)

    def solve(
        self,
        type: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        callback_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
    ) -> CaptchaSolution:
        """
        Blocking solve: submit the task, then poll the result endpoint honouring
        the API's ``retry_after`` until the task is ``ready``/``failed`` or
        ``timeout_sec`` elapses. Returns a CaptchaSolution, or raises EvesesError
        on failure/timeout.
        """
        headers: Dict[str, str] = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        body: Dict[str, Any] = {"type": type, "params": params or {}}
        if callback_url is not None:
            body["callback_url"] = callback_url

        started = self._client.request(
            "POST",
            "/api/account/captcha/solve",
            json_body=body,
            headers=headers or None,
        )
        started = started if isinstance(started, dict) else {}

        task_id = int(started.get("task_id") or 0)
        price_micro_usd = started.get("price_micro_usd")
        price_micro_usd = int(price_micro_usd) if isinstance(price_micro_usd, int) else None
        retry_after = int(started.get("retry_after") or 5)
        deadline = time.time() + timeout_sec
        status = str(started.get("status") or "queued")

        if status in ("ready", "failed"):
            return self._finalise(task_id, status, started.get("solution"), started.get("error"), price_micro_usd)

        while True:
            self._sleep(retry_after)

            res = self._client.request(
                "GET",
                f"/api/account/captcha/result/{task_id}",
            )
            res = res if isinstance(res, dict) else {}
            retry_after = int(res.get("retry_after") or retry_after)
            status = str(res.get("status") or "processing")

            if status in ("ready", "failed"):
                return self._finalise(task_id, status, res.get("solution"), res.get("error"), price_micro_usd)

            if time.time() >= deadline:
                raise EvesesError(f"Captcha task {task_id} timed out before resolving", 0)

    def _finalise(
        self,
        task_id: int,
        status: str,
        solution: Any,
        error: Any,
        price_micro_usd: Optional[int],
    ) -> CaptchaSolution:
        solution = solution if isinstance(solution, str) else None
        error = error if isinstance(error, str) else None
        if status == "failed":
            raise EvesesError(f"Captcha task {task_id} failed: {error or 'unknown error'}", 0)
        return CaptchaSolution(
            task_id=task_id,
            status=status,
            solution=solution,
            error=error,
            price_micro_usd=price_micro_usd,
        )
