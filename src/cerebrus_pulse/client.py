"""Cerebrus Pulse API client."""

from __future__ import annotations

import httpx

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
)

DEFAULT_BASE_URL = "https://api.cerebruspulse.xyz"
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
        base_url: API base URL (default: https://api.cerebruspulse.xyz)
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
                    "See https://cerebruspulse.xyz/guides/x402-payments"
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
        """Get multi-timeframe technical analysis. Cost: $0.025 USDC.

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
        """Get complete analysis bundle. Cost: $0.05 USDC (9% discount).

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")
            timeframes: Comma-separated timeframes (15m, 1h, 4h)

        Returns:
            BundleResponse with pulse, sentiment, and funding data
        """
        data = self._get(f"/bundle/{coin}", params={"timeframes": timeframes})
        return BundleResponse.from_dict(data)

    def screener(self, top_n: int = 30) -> ScreenerResponse:
        """Scan all coins for top signals. Cost: $0.06 USDC.

        Args:
            top_n: Number of top coins to return (1-30, default: 30)

        Returns:
            ScreenerResponse with ranked coins and their signals
        """
        data = self._get("/screener", params={"top_n": top_n})
        return ScreenerResponse.from_dict(data)

    def oi(self, coin: str) -> OIResponse:
        """Get open interest analysis. Cost: $0.015 USDC.

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")

        Returns:
            OIResponse with OI delta, percentile, trend, and divergence
        """
        data = self._get(f"/oi/{coin}")
        return OIResponse.from_dict(data)

    def spread(self, coin: str) -> SpreadResponse:
        """Get spread and liquidity analysis. Cost: $0.015 USDC.

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")

        Returns:
            SpreadResponse with spread, slippage estimates, and liquidity score
        """
        data = self._get(f"/spread/{coin}")
        return SpreadResponse.from_dict(data)

    def correlation(self) -> CorrelationResponse:
        """Get BTC-alt correlation matrix. Cost: $0.05 USDC.

        Returns:
            CorrelationResponse with correlation matrix, regime, and sectors
        """
        data = self._get("/correlation")
        return CorrelationResponse.from_dict(data)

    def stress(self, limit: int = 10) -> StressResponse:
        """Get market stress index from cross-chain arbitrage detection. Cost: $0.015 USDC.

        Args:
            limit: Number of recent scans to analyze (1-50, default: 10)

        Returns:
            StressResponse with stress level/score, statistics, and recent scans
        """
        data = self._get("/arb", params={"limit": limit})
        return StressResponse.from_dict(data)

    def cex_dex(self, coin: str) -> CexDexResponse:
        """Get CEX-DEX price divergence. Cost: $0.02 USDC.

        Args:
            coin: Coin ticker (e.g., "ETH", "BTC", "LINK")

        Returns:
            CexDexResponse with divergence direction, spread, and interpretation
        """
        data = self._get(f"/cex-dex/{coin}")
        return CexDexResponse.from_dict(data)

    def basis(self, coin: str) -> BasisResponse:
        """Get Chainlink basis analysis (HL perp vs Chainlink spot). Cost: $0.02 USDC.

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")

        Returns:
            BasisResponse with basis in bps, direction, signal, and interpretation
        """
        data = self._get(f"/basis/{coin}")
        return BasisResponse.from_dict(data)

    def depeg(self) -> DepegResponse:
        """Get USDC collateral health monitor. Cost: $0.01 USDC.

        Returns:
            DepegResponse with USDC peg status, deviation, and infrastructure health
        """
        data = self._get("/depeg")
        return DepegResponse.from_dict(data)

    def liquidations(self, coin: str) -> LiquidationsResponse:
        """Get estimated liquidation heatmap. Cost: $0.03 USDC.

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")

        Returns:
            LiquidationsResponse with long/short zones, cascade risk, and nearest cluster
        """
        data = self._get(f"/liquidations/{coin}")
        return LiquidationsResponse.from_dict(data)
