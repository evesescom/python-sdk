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
from .emails import (
    EmailAddress,
    EmailDomain,
    EmailDomainsResponse,
    EmailMessage,
    EmailMessagesPage,
    EmailQuote,
    Emails,
)
from .exceptions import (
    EvesesAuthError,
    EvesesError,
    EvesesForbiddenError,
    EvesesNotFoundError,
    EvesesRateLimitError,
    EvesesServerError,
    EvesesValidationError,
)
from .proxies import (
    Proxies,
    ProxyEndpoints,
    ProxyOrder,
    ProxyOverview,
    ProxyQuote,
    ProxySubscription,
    ResidentialAccess,
    ResidentialPackage,
    ResidentialPackagesResponse,
    StaticCatalogResponse,
    StaticLocation,
    StaticPlan,
    StaticProduct,
)
from .wallet import Wallet, WalletBalance
from .web_unblocker import (
    WebUnblocker,
    WebUnblockerAccess,
    WebUnblockerOrder,
    WebUnblockerOverview,
    WebUnblockerPackage,
    WebUnblockerPackagesResponse,
    WebUnblockerQuote,
    WebUnblockerSubscription,
)
from .webhooks import Webhooks, verify_webhook

__version__ = "0.2.0"

__all__ = [
    "Eveses",
    "Activations",
    "Catalog",
    "Wallet",
    "Proxies",
    "WebUnblocker",
    "Emails",
    "Webhooks",
    "verify_webhook",
    "Order",
    "OrderSms",
    "OrderSmsBundle",
    "WalletBalance",
    "ProxyOverview",
    "ProxyOrder",
    "ProxySubscription",
    "ProxyQuote",
    "ProxyEndpoints",
    "ResidentialAccess",
    "ResidentialPackage",
    "ResidentialPackagesResponse",
    "StaticProduct",
    "StaticPlan",
    "StaticLocation",
    "StaticCatalogResponse",
    "WebUnblockerOverview",
    "WebUnblockerAccess",
    "WebUnblockerOrder",
    "WebUnblockerSubscription",
    "WebUnblockerPackage",
    "WebUnblockerPackagesResponse",
    "WebUnblockerQuote",
    "EmailAddress",
    "EmailMessage",
    "EmailMessagesPage",
    "EmailDomain",
    "EmailDomainsResponse",
    "EmailQuote",
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
