# Cerebrus Pulse Python SDK

Python SDK for [Cerebrus Pulse](https://cerebruspulse.xyz) — real-time crypto intelligence API for 50+ Hyperliquid perpetuals. Pay with USDC on Base or Solana via x402.

## Install

```bash
pip install cerebrus-pulse
```

## Quick Start

```python
from cerebrus_pulse import CerebrusPulse

client = CerebrusPulse()

# Free — list available coins
coins = client.coins()
print(f"Available: {len(coins)} coins")

# Free — check health
health = client.health()
print(f"Status: {health['status']}")
```

## Paid Endpoints (x402)

Paid endpoints require [x402 micropayments](https://cerebruspulse.xyz/guides/x402-payments) — USDC on Base or Solana. No API keys or subscriptions needed.

```python
# Technical analysis — $0.02 USDC
pulse = client.pulse("BTC", timeframes="1h,4h")
print(f"Price: ${pulse.price}")
print(f"RSI (1h): {pulse.timeframes['1h'].indicators.rsi_14}")
print(f"Trend: {pulse.timeframes['1h'].indicators.trend.label}")
print(f"Confluence: {pulse.confluence.score} ({pulse.confluence.bias})")
print(f"Regime: {pulse.regime.current}")

# Sentiment — $0.01 USDC
sentiment = client.sentiment()
print(f"Market: {sentiment.overall} (score: {sentiment.score})")

# Funding rates — $0.01 USDC
funding = client.funding("ETH", lookback_hours=48)
print(f"ETH funding: {funding.annualized_pct}% annualized")

# Bundle (all data, 17% discount) — $0.04 USDC
bundle = client.bundle("SOL")
print(f"SOL price: ${bundle.pulse.price}")
print(f"Sentiment: {bundle.sentiment.overall}")
print(f"Funding: {bundle.funding.annualized_pct}%")

# Market Stress Index — $0.02 USDC
stress = client.arb()
print(f"Stress: {stress.stress_level} ({stress.stress_score:.2f})")

# CEX-DEX divergence — $0.01 USDC
div = client.cex_dex("ETH")
print(f"ETH divergence: {div.divergence_bps} bps ({div.direction})")
```

## Response Models

All paid endpoints return typed dataclass objects:

- `PulseResponse` — Technical indicators, derivatives, regime, confluence
- `SentimentResponse` — Overall sentiment, fear/greed, momentum, funding bias
- `FundingResponse` — Current rate, historical stats, rate history
- `BundleResponse` — All three combined
- `ArbResponse` — Market Stress Index with stress level and score
- `CexDexResponse` — CEX-DEX divergence with basis points and direction

Access raw JSON via the `.raw` attribute on any response.

## Error Handling

```python
from cerebrus_pulse import CerebrusPulse
from cerebrus_pulse.client import PaymentRequired, RateLimited, CerebrusPulseError

client = CerebrusPulse()

try:
    pulse = client.pulse("BTC")
except PaymentRequired:
    print("Need x402 wallet setup — see docs")
except RateLimited:
    print("Too many requests — back off")
except CerebrusPulseError as e:
    print(f"API error: {e.status_code} — {e.detail}")
```

## Links

- [Documentation](https://cerebruspulse.xyz/overview)
- [API Reference](https://cerebruspulse.xyz/api/pulse)
- [x402 Payment Guide](https://cerebruspulse.xyz/guides/x402-payments)
- [OpenAPI Spec](https://cerebruspulse.xyz/openapi.yaml)
- [MCP Server](https://github.com/0xsl1m/cerebrus-pulse-mcp) — Use with Claude Desktop, Cursor, etc.

## Disclaimer

Cerebrus Pulse provides market data and technical indicators for **informational purposes only**. Nothing provided by this SDK or the underlying API constitutes financial advice, investment advice, or trading advice. AI-generated analysis, signals, and sentiment labels are algorithmic outputs — not recommendations to buy, sell, or hold any asset. Cryptocurrency trading involves substantial risk of loss. You are solely responsible for your own trading decisions.

## License

MIT
