"""The typed models must read what the API actually returns (F070).

``fixtures/engine_responses.json`` is real engine output: a copy of the
gateway's ``service/response_examples.json``, which
``scripts/build_response_examples.py`` generates by running the unmodified
``engine/pulse_engine.py`` on captured feeds (gateway commit 13f7e57). The
gateway passes engine output through unchanged, and the engine shape is the
canonical contract. Refresh the copy after any engine change.

Before 0.4.0 the /funding and /sentiment parsers read a nested shape the
engine never sends, and every missing field defaulted to 0 or "unknown", so a
paid call returned plausible-looking zeros.
"""

import json
from pathlib import Path

import pytest

from cerebrus_pulse.models import (
    BasisResponse,
    BundleResponse,
    CexDexResponse,
    CorrelationResponse,
    DepegResponse,
    FundingResponse,
    LiquidationsResponse,
    OIResponse,
    PulseResponse,
    ScreenerResponse,
    SentimentResponse,
    SpreadResponse,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "engine_responses.json").read_text(encoding="utf-8")
)
EXAMPLES = FIXTURE["examples"]

MODELS = {
    "pulse": PulseResponse,
    "sentiment": SentimentResponse,
    "funding": FundingResponse,
    "bundle": BundleResponse,
    "screener": ScreenerResponse,
    "oi": OIResponse,
    "spread": SpreadResponse,
    "correlation": CorrelationResponse,
    "basis": BasisResponse,
    "cex-dex": CexDexResponse,
    "depeg": DepegResponse,
    "liquidations": LiquidationsResponse,
}

# Per endpoint: keys a parser may look up that the engine legitimately omits
# from the fixture. None today.
OPTIONAL_KEYS: dict[str, set] = {}


class Recording(dict):
    """A dict that records every key a parser asks for but does not find."""

    def __init__(self, data: dict, missing: set, path: str = ""):
        super().__init__(data)
        self._missing = missing
        self._path = path

    def _wrap(self, key, value):
        where = f"{self._path}.{key}" if self._path else str(key)
        if isinstance(value, dict) and not isinstance(value, Recording):
            return Recording(value, self._missing, where)
        if isinstance(value, list):
            return [Recording(v, self._missing, f"{where}[]") if isinstance(v, dict) else v
                    for v in value]
        return value

    def get(self, key, default=None):
        if key not in self:
            self._missing.add(f"{self._path}.{key}" if self._path else key)
            return default
        return self._wrap(key, super().__getitem__(key))

    def __getitem__(self, key):
        return self._wrap(key, super().__getitem__(key))

    def items(self):
        return [(k, self._wrap(k, v)) for k, v in super().items()]


def test_fixture_is_real_engine_output():
    assert FIXTURE["_meta"]["generated_by"] == "scripts/build_response_examples.py"
    assert set(MODELS) <= set(EXAMPLES)


@pytest.mark.parametrize("endpoint", sorted(MODELS))
def test_parser_reads_only_fields_the_engine_sends(endpoint):
    missing: set = set()
    MODELS[endpoint].from_dict(Recording(EXAMPLES[endpoint], missing))
    assert missing <= OPTIONAL_KEYS.get(endpoint, set()), (
        f"{endpoint}: the SDK reads keys the engine does not send: {sorted(missing)}"
    )


# ── /funding ────────────────────────────────────────────────────────────────

def test_funding_parses_the_flat_engine_shape():
    raw = EXAMPLES["funding"]
    f = FundingResponse.from_dict(raw)
    assert f.coin == "BTC"
    assert f.current_rate == raw["current"] == 1.25e-05
    assert f.average_rate == raw["avg_funding_rate"]
    assert f.min_rate == raw["min"]
    assert f.max_rate == raw["max"]
    assert f.annualized_pct == raw["annualized_pct"]
    assert f.lookback_hours == 24
    assert f.records == 23
    assert f.positive_pct == 82.6
    assert f.meta["offering"] == "pulse_funding"
    assert f.raw is raw


def test_funding_missing_fields_are_none_not_zero():
    f = FundingResponse.from_dict({"coin": "BTC"})
    assert f.current_rate is None
    assert f.average_rate is None
    assert f.min_rate is None
    assert f.max_rate is None
    assert f.annualized_pct is None
    assert f.lookback_hours is None
    assert f.records is None
    assert f.positive_pct is None


def test_funding_no_longer_reads_the_undocumented_nested_shape():
    # The pre-0.4.0 parser read {"funding": {"current_rate": ...}}. The engine
    # never sends that, so it must not be mistaken for data.
    f = FundingResponse.from_dict({"funding": {"current_rate": 0.5}})
    assert f.current_rate is None


# ── /sentiment ──────────────────────────────────────────────────────────────

def test_sentiment_parses_the_bucketed_label():
    raw = EXAMPLES["sentiment"]
    s = SentimentResponse.from_dict(raw)
    assert s.label == "bullish"
    assert s.overall == "bullish"
    assert s.as_of == raw["sentiment"]["as_of"]
    assert s.meta["offering"] == "pulse_sentiment"


def test_sentiment_withholds_raw_scores():
    # The engine publishes a label only (Sentinel audit H1); the SDK must not
    # invent a numeric score.
    s = SentimentResponse.from_dict(EXAMPLES["sentiment"])
    assert not hasattr(s, "score")


def test_sentiment_missing_fields_are_none():
    s = SentimentResponse.from_dict({})
    assert s.label is None
    assert s.as_of is None


# ── /bundle ─────────────────────────────────────────────────────────────────

def test_bundle_funding_and_sentiment_match_the_standalone_parsers():
    raw = EXAMPLES["bundle"]
    b = BundleResponse.from_dict(raw)
    assert b.coin == "BTC"
    assert b.pulse.price == raw["price"]["current"]
    assert b.funding.coin == "BTC"
    assert b.funding.current_rate == raw["funding_24h"]["current"]
    assert b.funding.average_rate == raw["funding_24h"]["avg_funding_rate"]
    assert b.funding.records == raw["funding_24h"]["records"]
    assert b.sentiment.label == raw["sentiment"]["label"]
    assert b.sentiment.as_of == raw["sentiment"]["as_of"]


def test_bundle_with_unavailable_funding_reports_none():
    raw = dict(EXAMPLES["bundle"], funding_24h={"note": "unavailable"})
    b = BundleResponse.from_dict(raw)
    assert b.funding.current_rate is None
    assert b.funding.annualized_pct is None


def test_bundle_does_not_mutate_its_input():
    raw = json.loads(json.dumps(EXAMPLES["bundle"]))
    before = json.dumps(raw, sort_keys=True)
    BundleResponse.from_dict(raw)
    assert json.dumps(raw, sort_keys=True) == before


# ── Other endpoints: spot checks on real values ─────────────────────────────

def test_pulse_reads_price_and_confluence():
    p = PulseResponse.from_dict(EXAMPLES["pulse"])
    assert p.price == 84512.5
    assert p.confluence.score == 0.62
    assert p.timeframes["1h"].indicators.rsi_14 == 49.16


def test_liquidations_reads_zones():
    liq = LiquidationsResponse.from_dict(EXAMPLES["liquidations"])
    assert liq.summary.cascade_risk == "HIGH"
    assert liq.long_zones[0].leverage == "50x"
