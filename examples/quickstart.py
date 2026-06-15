"""
quickstart.py — Hello-world for the Eveses Python SDK.

Run me
------
    pip install -e .                  # from sdk/python/
    export EVESES_API_KEY=sk_live_xxx # your sk_ token from the dashboard
    python examples/quickstart.py

What it does
------------
1. Builds an authenticated client (Bearer Sanctum API-key token).
2. Reads your wallet balance, so you can see currency + available funds.
3. Lists service codes available for one country (so you know what to ask for).
4. Buys ONE activation with a randomly-generated idempotency key.

Idempotency note
----------------
We send a random `idempotency_key` so this script is safe to retry on
network blips: the API will return the SAME order on a retry instead of
charging you twice for two numbers. In production, generate the key once
per *user intent* (e.g. when the user clicks "Buy"), not per HTTP attempt.
"""

from __future__ import annotations

import os
import uuid

from eveses import (
    Eveses,
    EvesesAuthError,
    EvesesError,
    EvesesValidationError,
)

API_KEY = os.environ.get("EVESES_API_KEY", "sk_test_placeholder")
COUNTRY = os.environ.get("EVESES_COUNTRY", "ua")
SERVICE = os.environ.get("EVESES_SERVICE", "telegram")


def main() -> None:
    # The constructor only validates that the key is non-empty; the first
    # actual network call is where 401s surface. We catch the whole
    # EvesesError family at the boundary.
    client = Eveses(api_key=API_KEY)

    try:
        # Wallet balance is reported in MINOR units (cents). Note the
        # distinction: `available_balance` is what you can spend right now;
        # `held_balance` is reserved against in-flight orders and unlocks
        # when those orders finish or expire.
        wallet = client.wallet.balance()
        print(
            f"Wallet: {wallet.available_balance / 100:.2f} {wallet.currency} "
            f"available (held: {wallet.held_balance / 100:.2f})"
        )

        # The "services" catalog endpoint returns the global product list
        # for the current mode; `country` is informational on v1.
        services = client.catalog.services(mode="activation", country=COUNTRY)
        print(f"{len(services.services)} services available in mode={services.mode}")
        if SERVICE not in services.services:
            print(f"Warning: '{SERVICE}' not in catalog — request may 404.")

        # The idempotency key MUST be stable across retries of the same
        # intent. uuid4() is fine here because we only call create() once.
        order = client.activations.create(
            country=COUNTRY,
            service=SERVICE,
            mode="activation",
            idempotency_key=str(uuid.uuid4()),
        )
        print(f"Created order {order.order_id}: phone={order.phone} status={order.status}")
        print("Next: poll client.activations.sms(order.order_id) for the code.")

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
