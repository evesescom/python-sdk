"""
marketplace.py — Browse the Eveses marketplace and (optionally) buy.

Run me
------
    pip install -e .                  # from sdk/python/
    export EVESES_API_KEY=sk_live_xxx # your sk_ token from the dashboard
    python examples/marketplace.py

What it does
------------
1. Builds an authenticated client (Bearer Sanctum API-key token).
2. Lists the filter facets for one category (country/origin/format/twofa).
3. Lists the available marketplace categories.
4. Browses the normalized catalog grouped by attributes, and prints a few
   groups with their `prices_cents` variants.

Grouping note
-------------
`group_by="attributes"` folds same-type SKUs into groups that each carry a
`prices_cents` list of variants — handy for a "one card per product, price
ladder inside" UI. Use `group_by="country"` to pivot by geography instead.
The browse endpoints are public; only quote/buy/reveal need the API key.
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
CATEGORY = os.environ.get("EVESES_MARKETPLACE_CATEGORY", "accounts")
COUNTRY = os.environ.get("EVESES_MARKETPLACE_COUNTRY", "US")
ORIGIN = os.environ.get("EVESES_MARKETPLACE_ORIGIN", "autoreg")


def main() -> None:
    # The constructor only validates that the key is non-empty; the first
    # actual network call is where 401s surface. We catch the whole
    # EvesesError family at the boundary.
    client = Eveses(api_key=API_KEY)

    try:
        # Filter facets tell you which country/origin/format/twofa values are
        # actually selectable for this category — drive dropdowns from these.
        filters = client.marketplace.filters(CATEGORY)
        print(f"Filters for '{CATEGORY}': {sorted(filters.keys())}")

        # The category list is what powers the top-level marketplace nav.
        categories = client.marketplace.categories()
        cats = categories.get("categories", categories)
        print(f"Categories: {cats}")

        # Browse the catalog grouped by attributes: same-type products collapse
        # into groups, each carrying a `prices_cents` list of variants.
        catalog = client.marketplace.catalog(
            category=CATEGORY,
            country=COUNTRY,
            origin=ORIGIN,
            group_by="attributes",
        )
        groups = catalog.get("groups", [])
        print(f"{len(groups)} group(s) in {CATEGORY}/{COUNTRY}/{ORIGIN}:")
        for group in groups[:5]:
            prices = group.get("prices_cents", [])
            label = group.get("title") or group.get("sku") or group.get("attributes")
            print(f"  {label}: prices_cents={prices}")

        # --- Buy + reveal (uncomment to actually purchase) --------------------
        # Pick a concrete SKU from the catalog, quote it, buy it, then reveal
        # the delivered goods. reveal() returns the credentials / files.
        #
        # import uuid
        # sku = groups[0]["prices_cents"][0]["sku"]  # cheapest variant, e.g.
        # quote = client.marketplace.quote(CATEGORY, sku)
        # print(f"Quote: {quote}")
        # order = client.marketplace.buy(
        #     CATEGORY,
        #     sku,
        #     quantity=1,
        #     idempotency_key=str(uuid.uuid4()),
        # )
        # print(f"Bought order {order.get('uuid')}: {order.get('status')}")
        # goods = client.marketplace.reveal(order["uuid"])
        # print(f"Revealed: {goods}")

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
