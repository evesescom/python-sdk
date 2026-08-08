"""
proxy_locations.py — Explore residential proxy targeting geo.

Run me
------
    pip install -e .                  # from sdk/python/
    export EVESES_API_KEY=sk_live_xxx # your sk_ token from the dashboard
    python examples/proxy_locations.py

What it does
------------
1. Builds an authenticated client (Bearer Sanctum API-key token).
2. Lists the available residential targeting (countries/regions/sets).
3. Drills into ONE country for its state/city (and ISP) breakdown.

Targeting note
--------------
`locations("residential")` is the country-level index; `locations_detail(country)`
is the per-country drill-down you use to build a "US → state → city" picker.
The `geo.tokens` block tells you how to phrase the targeting on the wire.
"""

from __future__ import annotations

import os

from eveses import (
    Eveses,
    EvesesAuthError,
    EvesesError,
    EvesesValidationError,
)

API_KEY = os.environ.get("EVESES_API_KEY", "sk_test_placeholder")
COUNTRY = os.environ.get("EVESES_PROXY_COUNTRY", "us")


def main() -> None:
    # The constructor only validates that the key is non-empty; the first
    # actual network call is where 401s surface. We catch the whole
    # EvesesError family at the boundary.
    client = Eveses(api_key=API_KEY)

    try:
        # Country-level residential targeting index.
        locations = client.proxy.locations("residential")
        countries = locations.get("countries", locations)
        print(f"Residential targeting index: {countries}")

        # Per-country drill-down: states, cities, and (where available) ISPs.
        detail = client.proxy.locations_detail(COUNTRY)
        geo = detail.get("geo", {})

        states = geo.get("states", [])
        print(f"{len(states)} state(s) in '{COUNTRY}':")
        for state in states[:10]:
            print(f"  {state.get('code')}: {state.get('name')}")

        cities = geo.get("cities", [])
        print(f"{len(cities)} city(ies) in '{COUNTRY}':")
        for city in cities[:10]:
            print(f"  {city.get('code')}: {city.get('name')}")

    except EvesesAuthError:
        print("Auth failed — check EVESES_API_KEY (must start with sk_).")
    except EvesesValidationError as exc:
        # Validation errors carry per-field details under .errors.
        print(f"Validation failed: {exc.message}")
        if exc.errors:
            for field, msgs in exc.errors.items():
                print(f"  {field}: {', '.join(msgs)}")
    except EvesesError as exc:
        # Catches rate-limit, 5xx, network errors, etc.
        print(f"SDK error ({exc.status}): {exc.message}")


if __name__ == "__main__":
    main()
