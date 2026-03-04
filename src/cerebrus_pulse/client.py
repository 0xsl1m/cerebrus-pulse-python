"""Cerebrus Pulse API client."""

from __future__ import annotations

import httpx

from cerebrus_pulse.models import (
    PulseResponse,
    SentimentResponse,
    FundingResponse,
    BundleResponse,
)

DEFAULT_BASE_URL = "https://pulse.openclaw.ai"
DEFAULT_TIMEOUT = 30.0


class CerebrusPulseError(Exception):
    """Base exception for Cerebrus Pulse errors."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class PaymentRequired(CerebrusPulseError):
    """Raised when x402 payment is needed but no wallet is configured."""

    def __init__(self, detail: str = "x402 payment required"):
        super().__init__(402, detail)


class RateLimited(CerebrusPulseError):
    """Raised when rate limit is exceeded."""

    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(429, detail)


class CerebrusPulse:
    """Client for the Cerebrus Pulse crypto intelligence API.

    Args:
        base_url: API base URL (default: https://pulse.openclaw.ai)
        timeout: Request timeout in seconds (default: 30)

    Example::

        from cerebrus_pulse import CerebrusPulse

        client = CerebrusPulse()

        # Free endpoints
        coins = client.coins()
        print(coins)

        # Paid endpoint (requires x402 payment)
        pulse = client.pulse("BTC", timeframes="1h,4h")
        print(f"BTC RSI: {pulse.timeframes['1h'].indicators.rsi_14}")
        print(f"Confluence: {pulse.confluence.score} ({pulse.confluence.bias})")
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={"User-Agent": "cerebrus-pulse-python/0.1.0"},
        )

    def _get(self, path: str, params: dict | None = None) -> dict:
        with self._client() as client:
            resp = client.get(path, params=params)

            if resp.status_code == 402:
                raise PaymentRequired(
                    "x402 payment required. Set up a Base wallet with USDC and use the x402 SDK. "
                    "See https://pulse.openclaw.ai/guides/x402-payments"
                )

            if resp.status_code == 429:
                detail = resp.json().get("detail", "Rate limit exceeded") if "application/json" in resp.headers.get("content-type", "") else resp.text
                raise RateLimited(detail)

            if resp.status_code >= 400:
                detail = resp.text[:500]
                raise CerebrusPulseError(resp.status_code, detail)

            return resp.json()

    # ── Free endpoints ───────────────────────────────────────────────────

    def health(self) -> dict:
        """Check gateway health status. Free."""
        return self._get("/health")

    def coins(self) -> list[str]:
        """List available coin tickers. Free."""
        data = self._get("/coins")
        return data.get("coins", [])

    # ── Paid endpoints (x402) ────────────────────────────────────────────

    def pulse(self, coin: str, timeframes: str = "1h,4h") -> PulseResponse:
        """Get multi-timeframe technical analysis. Cost: $0.02 USDC.

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")
            timeframes: Comma-separated timeframes (15m, 1h, 4h)

        Returns:
            PulseResponse with indicators, derivatives, regime, confluence
        """
        data = self._get(f"/pulse/{coin}", params={"timeframes": timeframes})
        return PulseResponse.from_dict(data)

    def sentiment(self) -> SentimentResponse:
        """Get market sentiment analysis. Cost: $0.01 USDC."""
        data = self._get("/sentiment")
        return SentimentResponse.from_dict(data)

    def funding(self, coin: str, lookback_hours: int = 24) -> FundingResponse:
        """Get funding rate analysis. Cost: $0.01 USDC.

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")
            lookback_hours: Hours of historical data (1-168)

        Returns:
            FundingResponse with current rate, history, and stats
        """
        data = self._get(f"/funding/{coin}", params={"lookback_hours": lookback_hours})
        return FundingResponse.from_dict(data)

    def bundle(self, coin: str, timeframes: str = "1h,4h") -> BundleResponse:
        """Get complete analysis bundle. Cost: $0.04 USDC (20% discount).

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")
            timeframes: Comma-separated timeframes (15m, 1h, 4h)

        Returns:
            BundleResponse with pulse, sentiment, and funding data
        """
        data = self._get(f"/bundle/{coin}", params={"timeframes": timeframes})
        return BundleResponse.from_dict(data)
