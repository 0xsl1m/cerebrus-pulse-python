"""Response models for Cerebrus Pulse API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Bollinger:
    upper: float
    middle: float
    lower: float
    width_pct: float
    position_pct: float

    @classmethod
    def from_dict(cls, d: dict) -> Bollinger:
        return cls(
            upper=d.get("upper", 0),
            middle=d.get("middle", 0),
            lower=d.get("lower", 0),
            width_pct=d.get("width_pct", 0),
            position_pct=d.get("position_pct", 0),
        )


@dataclass
class Trend:
    direction: int  # 1=bullish, -1=bearish, 0=neutral
    label: str
    ema_stack: str

    @classmethod
    def from_dict(cls, d: dict) -> Trend:
        return cls(
            direction=d.get("direction", 0),
            label=d.get("label", "unknown"),
            ema_stack=d.get("ema_stack", "unknown"),
        )

    @property
    def is_bullish(self) -> bool:
        return self.direction > 0

    @property
    def is_bearish(self) -> bool:
        return self.direction < 0


@dataclass
class Indicators:
    rsi_14: float | None
    rsi_zone: str
    atr_14: float | None
    atr_pct: float | None
    ema_20: float | None
    ema_50: float | None
    ema_200: float | None
    vwap_20: float | None
    zscore_100: float | None
    bollinger: Bollinger | None
    trend: Trend | None

    @classmethod
    def from_dict(cls, d: dict) -> Indicators:
        boll = Bollinger.from_dict(d["bollinger"]) if d.get("bollinger") else None
        trend = Trend.from_dict(d["trend"]) if d.get("trend") else None
        return cls(
            rsi_14=d.get("rsi_14"),
            rsi_zone=d.get("rsi_zone", "unknown"),
            atr_14=d.get("atr_14"),
            atr_pct=d.get("atr_pct"),
            ema_20=d.get("ema_20"),
            ema_50=d.get("ema_50"),
            ema_200=d.get("ema_200"),
            vwap_20=d.get("vwap_20"),
            zscore_100=d.get("zscore_100"),
            bollinger=boll,
            trend=trend,
        )


@dataclass
class Derivatives:
    funding_rate: float | None = None
    funding_annualized_pct: float | None = None
    open_interest: float | None = None
    impact_bid: float | None = None
    impact_ask: float | None = None
    spread_bps: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Derivatives:
        return cls(
            funding_rate=d.get("funding_rate"),
            funding_annualized_pct=d.get("funding_annualized_pct"),
            open_interest=d.get("open_interest"),
            impact_bid=d.get("impact_bid"),
            impact_ask=d.get("impact_ask"),
            spread_bps=d.get("spread_bps"),
        )


@dataclass
class Regime:
    current: str
    as_of: int

    @classmethod
    def from_dict(cls, d: dict) -> Regime:
        return cls(current=d.get("current", "unknown"), as_of=d.get("as_of", 0))


@dataclass
class Confluence:
    score: float
    bias: str
    signals: dict[str, str] = field(default_factory=dict)
    bullish_count: int = 0
    bearish_count: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> Confluence:
        return cls(
            score=d.get("score", 0),
            bias=d.get("bias", "unknown"),
            signals=d.get("signals", {}),
            bullish_count=d.get("bullish_count", 0),
            bearish_count=d.get("bearish_count", 0),
        )

    @property
    def is_bullish(self) -> bool:
        return self.bias == "bullish"

    @property
    def is_bearish(self) -> bool:
        return self.bias == "bearish"


@dataclass
class TimeframeData:
    indicators: Indicators
    candle_freshness_seconds: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> TimeframeData:
        return cls(
            indicators=Indicators.from_dict(d.get("indicators", {})),
            candle_freshness_seconds=d.get("candle_freshness_seconds"),
        )


@dataclass
class PulseResponse:
    coin: str
    timestamp_iso: str
    price: float | None
    timeframes: dict[str, TimeframeData]
    derivatives: Derivatives
    regime: Regime
    confluence: Confluence
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> PulseResponse:
        tfs = {}
        for tf_key, tf_data in d.get("timeframes", {}).items():
            if "indicators" in tf_data:
                tfs[tf_key] = TimeframeData.from_dict(tf_data)
        return cls(
            coin=d.get("coin", ""),
            timestamp_iso=d.get("timestamp_iso", ""),
            price=d.get("price", {}).get("current"),
            timeframes=tfs,
            derivatives=Derivatives.from_dict(d.get("derivatives", {})),
            regime=Regime.from_dict(d.get("regime", {})),
            confluence=Confluence.from_dict(d.get("confluence", {})),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class SentimentResponse:
    overall: str
    score: float
    fear_greed: str
    momentum: str
    funding_bias: str
    timestamp_iso: str
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> SentimentResponse:
        s = d.get("sentiment", {})
        labels = s.get("labels", {})
        return cls(
            overall=s.get("overall", "unknown"),
            score=s.get("score", 0),
            fear_greed=labels.get("fear_greed", "unknown"),
            momentum=labels.get("momentum", "unknown"),
            funding_bias=labels.get("funding_bias", "unknown"),
            timestamp_iso=d.get("timestamp_iso", ""),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class FundingSnapshot:
    timestamp: int
    rate: float


@dataclass
class FundingResponse:
    coin: str
    current_rate: float
    annualized_pct: float
    lookback_hours: int
    average_rate: float
    max_rate: float
    min_rate: float
    history: list[FundingSnapshot]
    timestamp_iso: str
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> FundingResponse:
        f = d.get("funding", {})
        history = [
            FundingSnapshot(timestamp=h.get("timestamp", 0), rate=h.get("rate", 0))
            for h in f.get("history", [])
        ]
        return cls(
            coin=d.get("coin", ""),
            current_rate=f.get("current_rate", 0),
            annualized_pct=f.get("annualized_pct", 0),
            lookback_hours=f.get("lookback_hours", 24),
            average_rate=f.get("average_rate", 0),
            max_rate=f.get("max_rate", 0),
            min_rate=f.get("min_rate", 0),
            history=history,
            timestamp_iso=d.get("timestamp_iso", ""),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class OIData:
    current: float
    delta_1h: float
    delta_4h: float
    delta_24h: float
    percentile: float | None
    trend: str
    price_oi_divergence: str

    @classmethod
    def from_dict(cls, d: dict) -> OIData:
        return cls(
            current=d.get("current", 0),
            delta_1h=d.get("delta_1h", 0),
            delta_4h=d.get("delta_4h", 0),
            delta_24h=d.get("delta_24h", 0),
            percentile=d.get("percentile"),
            trend=d.get("trend", "FLAT"),
            price_oi_divergence=d.get("price_oi_divergence", "NONE"),
        )


@dataclass
class OIResponse:
    coin: str
    timestamp_iso: str
    open_interest: OIData
    price: float | None
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> OIResponse:
        return cls(
            coin=d.get("coin", ""),
            timestamp_iso=d.get("timestamp_iso", ""),
            open_interest=OIData.from_dict(d.get("open_interest", {})),
            price=d.get("price"),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class SpreadData:
    bid_ask_spread_bps: float
    impact_bid: float
    impact_ask: float
    mid_price: float
    estimated_slippage_bps: dict[str, float]
    liquidity_score: int

    @classmethod
    def from_dict(cls, d: dict) -> SpreadData:
        return cls(
            bid_ask_spread_bps=d.get("bid_ask_spread_bps", 0),
            impact_bid=d.get("impact_bid", 0),
            impact_ask=d.get("impact_ask", 0),
            mid_price=d.get("mid_price", 0),
            estimated_slippage_bps=d.get("estimated_slippage_bps", {}),
            liquidity_score=d.get("liquidity_score", 0),
        )


@dataclass
class SpreadResponse:
    coin: str
    timestamp_iso: str
    spread: SpreadData
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> SpreadResponse:
        return cls(
            coin=d.get("coin", ""),
            timestamp_iso=d.get("timestamp_iso", ""),
            spread=SpreadData.from_dict(d.get("spread", {})),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class CorrelationResponse:
    timestamp_iso: str
    btc_correlation: dict[str, float | None]
    average_correlation: float | None
    regime: str
    sector_averages: dict[str, float]
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> CorrelationResponse:
        return cls(
            timestamp_iso=d.get("timestamp_iso", ""),
            btc_correlation=d.get("btc_correlation", {}),
            average_correlation=d.get("average_correlation"),
            regime=d.get("regime", "UNKNOWN"),
            sector_averages=d.get("sector_averages", {}),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class ScreenerCoin:
    coin: str
    signal_strength: float
    rsi_14: float | None
    rsi_zone: str
    trend: str
    zscore: float | None
    atr_pct: float | None
    vol_regime: str
    funding_rate: float | None
    funding_bias: str
    confluence_bias: str
    confluence_score: float
    oi_trend: str
    price: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> ScreenerCoin:
        return cls(
            coin=d.get("coin", ""),
            signal_strength=d.get("signal_strength", 0),
            rsi_14=d.get("rsi_14"),
            rsi_zone=d.get("rsi_zone", "unknown"),
            trend=d.get("trend", "unknown"),
            zscore=d.get("zscore"),
            atr_pct=d.get("atr_pct"),
            vol_regime=d.get("vol_regime", "UNKNOWN"),
            funding_rate=d.get("funding_rate"),
            funding_bias=d.get("funding_bias", "neutral"),
            confluence_bias=d.get("confluence_bias", "unknown"),
            confluence_score=d.get("confluence_score", 0),
            oi_trend=d.get("oi_trend", "FLAT"),
            price=d.get("price"),
        )


@dataclass
class ScreenerResponse:
    coins_scanned: int
    top_n: int
    results: list[ScreenerCoin]
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> ScreenerResponse:
        results = [ScreenerCoin.from_dict(r) for r in d.get("results", [])]
        return cls(
            coins_scanned=d.get("coins_scanned", 0),
            top_n=d.get("top_n", 0),
            results=results,
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class StressIndex:
    level: str  # LOW, MODERATE, HIGH, EXTREME
    score: float  # 0.0-1.0
    interpretation: str

    @classmethod
    def from_dict(cls, d: dict) -> StressIndex:
        return cls(
            level=d.get("level", "LOW"),
            score=d.get("score", 0.0),
            interpretation=d.get("interpretation", ""),
        )


@dataclass
class StressStatistics:
    scans_analyzed: int
    total_opportunities: int
    total_profitable: int
    avg_spread_bps: float
    max_spread_bps: float
    unique_tokens_involved: list[str]
    chain_routes: list[str]

    @classmethod
    def from_dict(cls, d: dict) -> StressStatistics:
        return cls(
            scans_analyzed=d.get("scans_analyzed", 0),
            total_opportunities=d.get("total_opportunities", 0),
            total_profitable=d.get("total_profitable", 0),
            avg_spread_bps=d.get("avg_spread_bps", 0),
            max_spread_bps=d.get("max_spread_bps", 0),
            unique_tokens_involved=d.get("unique_tokens_involved", []),
            chain_routes=d.get("chain_routes", []),
        )


@dataclass
class StressResponse:
    timestamp_iso: str
    stress_index: StressIndex
    statistics: StressStatistics
    recent_scans: list[dict[str, Any]]
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> StressResponse:
        return cls(
            timestamp_iso=d.get("timestamp_iso", ""),
            stress_index=StressIndex.from_dict(d.get("stress_index", {})),
            statistics=StressStatistics.from_dict(d.get("statistics", {})),
            recent_scans=d.get("recent_scans", []),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class Divergence:
    cex_price: float
    dex_price: float
    dex_source: str
    spread_bps: float
    spread_pct: float
    direction: str  # cex_premium or dex_premium
    interpretation: str

    @classmethod
    def from_dict(cls, d: dict) -> Divergence:
        return cls(
            cex_price=d.get("cex_price", 0),
            dex_price=d.get("dex_price", 0),
            dex_source=d.get("dex_source", "unknown"),
            spread_bps=d.get("spread_bps", 0),
            spread_pct=d.get("spread_pct", 0),
            direction=d.get("direction", "unknown"),
            interpretation=d.get("interpretation", ""),
        )


@dataclass
class CexDexResponse:
    token: str
    timestamp_iso: str
    divergence: Divergence
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> CexDexResponse:
        return cls(
            token=d.get("token", ""),
            timestamp_iso=d.get("timestamp_iso", ""),
            divergence=Divergence.from_dict(d.get("divergence", {})),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class BasisData:
    hl_oracle_px: float
    chainlink_spot_px: float
    basis_bps: float
    basis_pct: float
    direction: str  # hl_premium, hl_discount, aligned
    signal: str  # neutral, mildly_bullish, mildly_bearish, bearish_contrarian, bullish_contrarian
    interpretation: str

    @classmethod
    def from_dict(cls, d: dict) -> BasisData:
        return cls(
            hl_oracle_px=d.get("hl_oracle_px", 0),
            chainlink_spot_px=d.get("chainlink_spot_px", 0),
            basis_bps=d.get("basis_bps", 0),
            basis_pct=d.get("basis_pct", 0),
            direction=d.get("direction", "aligned"),
            signal=d.get("signal", "neutral"),
            interpretation=d.get("interpretation", ""),
        )


@dataclass
class BasisResponse:
    coin: str
    timestamp_iso: str
    basis: BasisData
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> BasisResponse:
        return cls(
            coin=d.get("coin", ""),
            timestamp_iso=d.get("timestamp_iso", ""),
            basis=BasisData.from_dict(d.get("basis", {})),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class UsdcHealth:
    price_usd: float
    deviation_bps: float
    deviation_pct: float
    peg_status: str  # HEALTHY, ELEVATED, WARNING, CRITICAL
    risk_level: str  # low, medium, high, critical
    interpretation: str

    @classmethod
    def from_dict(cls, d: dict) -> UsdcHealth:
        return cls(
            price_usd=d.get("price_usd", 1.0),
            deviation_bps=d.get("deviation_bps", 0),
            deviation_pct=d.get("deviation_pct", 0),
            peg_status=d.get("peg_status", "HEALTHY"),
            risk_level=d.get("risk_level", "low"),
            interpretation=d.get("interpretation", ""),
        )


@dataclass
class DepegResponse:
    timestamp_iso: str
    usdc: UsdcHealth
    infrastructure: dict[str, Any]
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> DepegResponse:
        return cls(
            timestamp_iso=d.get("timestamp_iso", ""),
            usdc=UsdcHealth.from_dict(d.get("usdc", {})),
            infrastructure=d.get("infrastructure", {}),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class LiquidationZone:
    price: float
    leverage: str
    estimated_liq_usd: int
    proximity_pct: float

    @classmethod
    def from_dict(cls, d: dict) -> LiquidationZone:
        return cls(
            price=d.get("price", 0),
            leverage=d.get("leverage", ""),
            estimated_liq_usd=d.get("estimated_liq_usd", 0),
            proximity_pct=d.get("proximity_pct", 0),
        )


@dataclass
class LiquidationSummary:
    cascade_risk: str  # LOW, MODERATE, HIGH, EXTREME
    total_oi_usd: int
    long_short_ratio: str
    total_at_risk_5pct: int
    nearest_cluster: dict[str, Any] | None

    @classmethod
    def from_dict(cls, d: dict) -> LiquidationSummary:
        return cls(
            cascade_risk=d.get("cascade_risk", "UNKNOWN"),
            total_oi_usd=d.get("total_oi_usd", 0),
            long_short_ratio=d.get("long_short_ratio", "50:50"),
            total_at_risk_5pct=d.get("total_at_risk_5pct", 0),
            nearest_cluster=d.get("nearest_cluster"),
        )


@dataclass
class LiquidationsResponse:
    coin: str
    timestamp_iso: str
    price: float | None
    long_zones: list[LiquidationZone]
    short_zones: list[LiquidationZone]
    summary: LiquidationSummary
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> LiquidationsResponse:
        zones = d.get("liquidation_zones", {})
        return cls(
            coin=d.get("coin", ""),
            timestamp_iso=d.get("timestamp_iso", ""),
            price=d.get("price"),
            long_zones=[LiquidationZone.from_dict(z) for z in zones.get("longs", [])],
            short_zones=[LiquidationZone.from_dict(z) for z in zones.get("shorts", [])],
            summary=LiquidationSummary.from_dict(d.get("summary", {})),
            meta=d.get("meta", {}),
            raw=d,
        )


@dataclass
class BundleResponse:
    coin: str
    timestamp_iso: str
    pulse: PulseResponse
    sentiment: SentimentResponse
    funding: FundingResponse
    meta: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> BundleResponse:
        # Bundle response has pulse data at top level (timeframes, confluence, etc.)
        # and sentiment/funding as nested keys
        coin = d.get("coin", "")
        ts = d.get("timestamp_iso", "")

        # Pulse data lives at the top level of the bundle response
        pulse_data = dict(d)  # shallow copy to avoid mutating input
        pulse_data.setdefault("coin", coin)
        pulse_data.setdefault("timestamp_iso", ts)

        # Sentiment: engine returns {"label": ..., "as_of": ...} under "sentiment"
        # SentimentResponse.from_dict expects {"sentiment": {"overall": ..., "score": ...}}
        raw_sent = d.get("sentiment", {})
        sentiment_data = {
            "sentiment": {
                "overall": raw_sent.get("label", "unknown"),
                "score": 0,
                "labels": {
                    "fear_greed": raw_sent.get("label", "unknown"),
                    "momentum": "unknown",
                    "funding_bias": "unknown",
                },
            },
            "timestamp_iso": ts,
        }

        # Funding: engine returns under "funding_24h" (not "funding")
        raw_fund = d.get("funding_24h", d.get("funding", {}))
        funding_data = {
            "funding": {
                "current_rate": raw_fund.get("current", 0),
                "annualized_pct": raw_fund.get("annualized_pct", 0),
                "lookback_hours": raw_fund.get("lookback_hours", 24),
                "average_rate": raw_fund.get("avg_funding_rate", 0),
                "max_rate": raw_fund.get("max", 0),
                "min_rate": raw_fund.get("min", 0),
                "history": [],
            },
            "coin": coin,
            "timestamp_iso": ts,
        }

        return cls(
            coin=coin,
            timestamp_iso=ts,
            pulse=PulseResponse.from_dict(pulse_data),
            sentiment=SentimentResponse.from_dict(sentiment_data),
            funding=FundingResponse.from_dict(funding_data),
            meta=d.get("meta", {}),
            raw=d,
        )
