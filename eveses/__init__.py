"""
eveses — Official Python SDK.

Quickstart:

    from eveses import Eveses
    client = Eveses(api_key="sk_…")
    order = client.activations.create(country="ua", service="telegram")
    wallet = client.wallet.balance()
    services = client.catalog.services(mode="activation", country="ua")

Webhook verification:

    from eveses import Webhooks
    ok = Webhooks.verify(raw_body, signature_header, secret, timestamp=ts_header)
"""

from .activations import Activations, Order, OrderSms, OrderSmsBundle
from .catalog import (
    Catalog,
    CatalogCountriesResponse,
    CatalogPricingDuration,
    CatalogPricingResponse,
    CatalogServiceWithDurations,
    CatalogServicesResponse,
)
from .client import Eveses
from .exceptions import (
    EvesesAuthError,
    EvesesError,
    EvesesForbiddenError,
    EvesesNotFoundError,
    EvesesRateLimitError,
    EvesesServerError,
    EvesesValidationError,
)
from .wallet import Wallet, WalletBalance
from .webhooks import Webhooks, verify_webhook

__version__ = "0.1.0"

__all__ = [
    "Eveses",
    "Activations",
    "Catalog",
    "Wallet",
    "Webhooks",
    "verify_webhook",
    "Order",
    "OrderSms",
    "OrderSmsBundle",
    "WalletBalance",
    "CatalogCountriesResponse",
    "CatalogServicesResponse",
    "CatalogPricingResponse",
    "CatalogServiceWithDurations",
    "CatalogPricingDuration",
    "EvesesError",
    "EvesesAuthError",
    "EvesesForbiddenError",
    "EvesesNotFoundError",
    "EvesesValidationError",
    "EvesesRateLimitError",
    "EvesesServerError",
    "__version__",
]
