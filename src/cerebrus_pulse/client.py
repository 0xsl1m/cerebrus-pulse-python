"""Cerebrus Pulse API client."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

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
from cerebrus_pulse.payment import (
    Payer,
    PaymentRefused,
    PaymentTerms,
    SpendGuard,
    build_payment_client,
    parse_payment_terms,
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
    """Raised when an endpoint needs an x402 payment that was not made.

    ``terms`` holds the payment options the API offered in its 402 (price,
    network, payTo), so a caller can decide whether and how to pay.
    """

    def __init__(self, detail: str = "x402 payment required",
                 terms: list[PaymentTerms] | None = None):
        super().__init__(402, detail)
        self.terms = list(terms or [])

    @property
    def price_usd(self) -> Decimal | None:
        """The USDC price the API asked for (its first priced offer), if known."""
        for term in self.terms:
            if term.price_usd is not None:
                return term.price_usd
        return None


class PaymentBlocked(PaymentRequired):
    """Raised when the client's spend limits refused to pay. Nothing was signed."""

    def __init__(self, reason: str, terms: list[PaymentTerms] | None = None):
        self.reason = reason
        super().__init__(f"x402 payment blocked by local spend limits: {reason}", terms)


class PaymentRejected(PaymentRequired):
    """Raised when a signed payment was sent and the API still answered 402."""


class PaymentFailed(PaymentRequired):
    """Raised when the x402 payment flow failed (malformed terms, signing or network error)."""


class RateLimited(CerebrusPulseError):
    """Raised when rate limit is exceeded."""

    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(429, detail)


class CerebrusPulse:
    """Client for the Cerebrus Pulse crypto intelligence API.

    Without a wallet, paid endpoints raise :class:`PaymentRequired` carrying
    the API's payment terms. With the ``[pay]`` extra installed and a wallet
    key, they pay automatically in USDC over x402, inside client-side spend
    limits (see :mod:`cerebrus_pulse.payment`).

    Args:
        base_url: API base URL (default: https://api.cerebruspulse.xyz)
        timeout: Request timeout in seconds (default: 30)
        wallet_key: Private key of a dedicated, low-balance Base wallet holding
            USDC. Enables automatic payment on Base. Needs ``[pay]``.
        solana_key: Base58 keypair of a Solana wallet holding USDC. Enables
            automatic payment on Solana. Needs ``[pay,svm]``, and a Solana payTo
            in ``allowed_pay_to_solana``.
        x402_client: Your own configured ``x402.x402ClientSync`` to pay with,
            instead of a key. The spend limits are added to it as a policy, so
            do not share one x402 client between CerebrusPulse instances.
        max_payment_usd: Cap on one payment (else env
            ``CEREBRUS_MAX_PAYMENT_USD``, else $0.10).
        max_spend_usd: Cap on the total this client signs (else env
            ``CEREBRUS_MAX_SPEND_USD``, else $1.00).
        allowed_pay_to: Base payTo addresses to pay (else env
            ``CEREBRUS_ALLOWED_PAYTO``, else the published Cerebrus payTo).
        allowed_pay_to_solana: Solana payTo addresses to pay (else env
            ``CEREBRUS_ALLOWED_PAYTO_SOLANA``, else none).

    Example::

        import os
        from cerebrus_pulse import CerebrusPulse

        client = CerebrusPulse(wallet_key=os.environ["CEREBRUS_WALLET_KEY"])

        # Free endpoints
        coins = client.coins()
        print(coins)

        # Paid endpoint, paid automatically via x402
        pulse = client.pulse("BTC", timeframes="1h,4h")
        print(f"BTC RSI: {pulse.timeframes['1h'].indicators.rsi_14}")
        print(f"Confluence: {pulse.confluence.score} ({pulse.confluence.bias})")
        print(f"Spent so far: ${client.spent_usd}")
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        *,
        wallet_key: str | None = None,
        solana_key: str | None = None,
        x402_client: Any = None,
        max_payment_usd: float | str | Decimal | None = None,
        max_spend_usd: float | str | Decimal | None = None,
        allowed_pay_to: str | list[str] | None = None,
        allowed_pay_to_solana: str | list[str] | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport: httpx.BaseTransport | None = None
        self._payer: Payer | None = None
        if wallet_key or solana_key or x402_client is not None:
            guard = SpendGuard.from_settings(
                max_payment_usd, max_spend_usd, allowed_pay_to, allowed_pay_to_solana
            )
            client = build_payment_client(guard, wallet_key, solana_key, x402_client)
            self._payer = Payer(client, guard)

    @property
    def can_pay(self) -> bool:
        """Whether paid endpoints are paid automatically."""
        return self._payer is not None

    @property
    def spent_usd(self) -> Decimal:
        """Total USDC this client has signed for (0 when it cannot pay)."""
        return self._payer.guard.spent_usd if self._payer is not None else Decimal(0)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={"User-Agent": "cerebrus-pulse-python/0.1.0"},
            transport=self._transport,
        )

    def _get(self, path: str, params: dict | None = None) -> dict:
        with self._client() as client:
            resp = client.get(path, params=params)

            if resp.status_code == 402 and self._payer is not None:
                terms = parse_payment_terms(resp)
                try:
                    resp = self._payer.pay(
                        resp, lambda headers: client.get(path, params=params, headers=headers)
                    )
                except PaymentRefused as e:
                    if e.reason is not None:
                        raise PaymentBlocked(e.reason, terms) from None
                    raise PaymentFailed(f"x402 payment attempt failed: {e.error}", terms) from e
                if resp.status_code == 402:
                    raise PaymentRejected(
                        "A signed x402 payment was sent but the API did not accept it. "
                        "Check the wallet holds enough USDC.",
                        parse_payment_terms(resp) or terms,
                    )

            if resp.status_code == 402:
                raise PaymentRequired(
                    "x402 payment required. Install the pay extra "
                    '(pip install "cerebrus-pulse[pay]") and pass wallet_key= to pay '
                    "automatically. See https://cerebruspulse.xyz/guides/x402-payments",
                    parse_payment_terms(resp),
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
        """Get the bucketed market sentiment label. Cost: $0.01 USDC.

        Returns:
            SentimentResponse with ``label`` (very_bearish ... very_bullish) and ``as_of``
        """
        data = self._get("/sentiment")
        return SentimentResponse.from_dict(data)

    def funding(self, coin: str, lookback_hours: int = 24) -> FundingResponse:
        """Get funding rate analysis. Cost: $0.01 USDC.

        Args:
            coin: Coin ticker (e.g., "BTC", "ETH", "SOL")
            lookback_hours: Hours of historical data (1-168)

        Returns:
            FundingResponse with the current, average, min and max rate,
            annualized %, sample count and share of positive samples
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
