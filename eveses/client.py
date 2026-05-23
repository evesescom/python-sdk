"""
Eveses client. Hand-rolled wrapper around `requests` with:
  - Bearer auth header
  - JSON serialisation
  - Idempotency-Key header passthrough
  - One automatic retry on 429 (using Retry-After if present)
  - Typed exceptions for non-2xx responses
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Mapping, Optional

import requests

from .exceptions import (
    EvesesAuthError,
    EvesesError,
    EvesesForbiddenError,
    EvesesNotFoundError,
    EvesesRateLimitError,
    EvesesServerError,
    EvesesValidationError,
)

DEFAULT_BASE_URL = "https://api.eveses.io"
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_USER_AGENT = "eveses-python/0.1.0"


class Eveses:
    """
    Top-level SDK client.

    Example:
        from eveses import Eveses
        client = Eveses(api_key=os.environ["EVESES_API_KEY"])
        order = client.activations.create(country="ua", service="telegram")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        session: Optional[requests.Session] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if not api_key:
            raise EvesesError("api_key is required", 0)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent
        self._session = session or requests.Session()
        self._default_headers = dict(default_headers or {})

        # Lazy import to avoid circular references at module-import time.
        from .activations import Activations
        from .catalog import Catalog
        from .wallet import Wallet
        from .webhooks import Webhooks

        self.activations = Activations(self)
        self.wallet = Wallet(self)
        self.catalog = Catalog(self)
        # Static-like helper. Also importable as `from eveses import Webhooks`.
        self.webhooks = Webhooks

    # -------------------------------------------------------------- request --
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """Send a single authenticated request and return parsed JSON."""
        url = self._build_url(path)
        merged_headers: Dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        merged_headers.update(self._default_headers)
        if headers:
            merged_headers.update(headers)
        if json_body is not None:
            merged_headers.setdefault("Content-Type", "application/json")

        body_str: Optional[str] = None
        if json_body is not None:
            body_str = json.dumps(json_body, separators=(",", ":"))

        return self._execute_with_retry(method, url, merged_headers, params, body_str)

    def _execute_with_retry(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Mapping[str, Any]],
        body: Optional[str],
        attempt: int = 0,
    ) -> Any:
        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                params=_clean_params(params),
                data=body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise EvesesError(f"Network error: {exc}", 0) from exc

        if response.status_code == 429 and attempt == 0:
            time.sleep(_parse_retry_after(response.headers.get("Retry-After")))
            return self._execute_with_retry(method, url, headers, params, body, attempt + 1)

        return self._parse_response(response)

    def _parse_response(self, response: requests.Response) -> Any:
        content_type = response.headers.get("Content-Type", "")
        parsed: Any
        if "application/json" in content_type:
            try:
                parsed = response.json()
            except ValueError:
                parsed = None
        else:
            parsed = response.text or None

        if response.ok:
            return parsed

        message = _extract_message(parsed) or response.reason or f"HTTP {response.status_code}"
        status = response.status_code

        if status == 401:
            raise EvesesAuthError(message, body=parsed)
        if status == 403:
            raise EvesesForbiddenError(message, body=parsed)
        if status == 404:
            raise EvesesNotFoundError(message, body=parsed)
        if status in (400, 422):
            raise EvesesValidationError(message, status, body=parsed)
        if status == 429:
            raise EvesesRateLimitError(
                message,
                retry_after=_parse_retry_after(response.headers.get("Retry-After")),
                body=parsed,
            )
        if status >= 500:
            raise EvesesServerError(message, status, body=parsed)
        raise EvesesError(message, status, body=parsed)

    # --------------------------------------------------------------- helpers --
    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"


def _clean_params(params: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if not params:
        return None
    return {k: v for k, v in params.items() if v is not None}


def _parse_retry_after(value: Optional[str]) -> float:
    if not value:
        return 1.0
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return 1.0
    if seconds < 0:
        return 1.0
    return float(min(seconds, 60))


def _extract_message(body: Any) -> Optional[str]:
    if isinstance(body, dict):
        msg = body.get("message")
        if isinstance(msg, str):
            return msg
        err = body.get("error")
        if isinstance(err, str):
            return err
    return None
