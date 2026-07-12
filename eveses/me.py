"""
Me namespace — the authenticated principal. Hits `/api/v1/me`. Carries the
existing account fields plus `abilities` (what THIS token can do) and
`features` (which product entry points to surface).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:  # pragma: no cover
    from .client import Eveses


@dataclass
class MeProfile:
    abilities: List[str] = field(default_factory=list)
    features: Dict[str, bool] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


class Me:
    def __init__(self, client: "Eveses") -> None:
        self._client = client

    def get(self) -> MeProfile:
        """Fetch the current principal, including `abilities` and `features`."""
        res = self._client.request("GET", "/api/v1/me")
        d = _unwrap(res)
        abilities_raw = d.get("abilities")
        abilities = [str(a) for a in abilities_raw] if isinstance(abilities_raw, list) else []
        features_raw = d.get("features")
        features = (
            {str(k): bool(v) for k, v in features_raw.items()}
            if isinstance(features_raw, dict)
            else {}
        )
        return MeProfile(abilities=abilities, features=features, raw=dict(d))

    def loyalty(self) -> Dict[str, Any]:
        """The caller's loyalty tier / weekly-spend status."""
        res = self._client.request("GET", "/api/v1/me/loyalty")
        return res if isinstance(res, dict) else {}


def _unwrap(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}
