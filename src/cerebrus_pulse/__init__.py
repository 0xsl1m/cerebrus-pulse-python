"""Cerebrus Pulse Python SDK — real-time crypto intelligence for Hyperliquid perpetuals."""

from importlib.metadata import PackageNotFoundError, version as _dist_version

from cerebrus_pulse.client import (
    INDICATIVE_PRICES_USD,
    CerebrusPulse,
    CerebrusPulseError,
    PaymentBlocked,
    PaymentFailed,
    PaymentRejected,
    PaymentRequired,
    RateLimited,
)
from cerebrus_pulse.payment import PaymentTerms, SpendGuard
from cerebrus_pulse.models import (
    PulseResponse,
    SentimentResponse,
    FundingResponse,
    BundleResponse,
    OIResponse,
    SpreadResponse,
    CorrelationResponse,
    ScreenerResponse,
    StressResponse,
    CexDexResponse,
    BasisResponse,
    DepegResponse,
    LiquidationsResponse,
    Confluence,
    Regime,
    Derivatives,
    Indicators,
    Trend,
    Bollinger,
)

try:
    __version__ = _dist_version("cerebrus-pulse")  # pyproject.toml is the one source
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = "unknown"
__all__ = [
    "CerebrusPulse",
    "INDICATIVE_PRICES_USD",
    "CerebrusPulseError",
    "PaymentRequired",
    "PaymentBlocked",
    "PaymentRejected",
    "PaymentFailed",
    "RateLimited",
    "PaymentTerms",
    "SpendGuard",
    "PulseResponse",
    "SentimentResponse",
    "FundingResponse",
    "BundleResponse",
    "OIResponse",
    "SpreadResponse",
    "CorrelationResponse",
    "ScreenerResponse",
    "StressResponse",
    "CexDexResponse",
    "BasisResponse",
    "DepegResponse",
    "LiquidationsResponse",
    "Confluence",
    "Regime",
    "Derivatives",
    "Indicators",
    "Trend",
    "Bollinger",
]
