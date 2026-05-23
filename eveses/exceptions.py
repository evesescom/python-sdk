"""
Exception hierarchy for the Eveses SDK.

Every non-2xx response is converted into an EvesesError subclass:
    400/422 -> EvesesValidationError
    401     -> EvesesAuthError
    403     -> EvesesForbiddenError
    404     -> EvesesNotFoundError
    429     -> EvesesRateLimitError (after the 1 auto-retry is exhausted)
    5xx     -> EvesesServerError
    other   -> EvesesError
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class EvesesError(Exception):
    """Base class for all SDK errors."""

    def __init__(
        self,
        message: str,
        status: int = 0,
        *,
        code: Optional[str] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.body = body

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.__class__.__name__}({self.status}): {self.message}"


class EvesesAuthError(EvesesError):
    def __init__(self, message: str = "Unauthenticated", body: Any = None) -> None:
        super().__init__(message, 401, code="unauthenticated", body=body)


class EvesesForbiddenError(EvesesError):
    def __init__(self, message: str = "Forbidden", body: Any = None) -> None:
        super().__init__(message, 403, code="forbidden", body=body)


class EvesesNotFoundError(EvesesError):
    def __init__(self, message: str = "Not found", body: Any = None) -> None:
        super().__init__(message, 404, code="not_found", body=body)


class EvesesValidationError(EvesesError):
    def __init__(self, message: str, status: int, body: Any = None) -> None:
        super().__init__(message or "Validation failed", status, code="validation_failed", body=body)
        self.errors: Optional[Dict[str, List[str]]] = None
        if isinstance(body, dict) and isinstance(body.get("errors"), dict):
            self.errors = body["errors"]


class EvesesRateLimitError(EvesesError):
    def __init__(
        self,
        message: str = "Rate limited",
        retry_after: Optional[float] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message, 429, code="rate_limited", body=body)
        self.retry_after = retry_after


class EvesesServerError(EvesesError):
    def __init__(self, message: str, status: int, body: Any = None) -> None:
        super().__init__(message or "Server error", status, code="server_error", body=body)
