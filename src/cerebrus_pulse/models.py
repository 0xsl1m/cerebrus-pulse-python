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
        # Bundle wraps pulse/sentiment/funding under their keys
        pulse_data = d.get("pulse", {})
        pulse_data["coin"] = d.get("coin", "")
        pulse_data["timestamp_iso"] = d.get("timestamp_iso", "")

        sentiment_data = {"sentiment": d.get("sentiment", {}), "timestamp_iso": d.get("timestamp_iso", "")}
        funding_data = {"funding": d.get("funding", {}), "coin": d.get("coin", ""), "timestamp_iso": d.get("timestamp_iso", "")}

        return cls(
            coin=d.get("coin", ""),
            timestamp_iso=d.get("timestamp_iso", ""),
            pulse=PulseResponse.from_dict(pulse_data),
            sentiment=SentimentResponse.from_dict(sentiment_data),
            funding=FundingResponse.from_dict(funding_data),
            meta=d.get("meta", {}),
            raw=d,
        )
