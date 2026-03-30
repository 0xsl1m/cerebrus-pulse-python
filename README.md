
```
     ░█████╗░███████╗██████╗░███████╗██████╗░██████╗░██╗░░░██╗░██████╗
     ██╔══██╗██╔════╝██╔══██╗██╔════╝██╔══██╗██╔══██╗██║░░░██║██╔════╝
     ██║░░╚═╝█████╗░░██████╔╝█████╗░░██████╦╝██████╔╝██║░░░██║╚█████╗░
     ██║░░██╗██╔══╝░░██╔══██╗██╔══╝░░██╔══██╗██╔══██╗██║░░░██║░╚═══██╗
     ╚█████╔╝███████╗██║░░██║███████╗██████╦╝██║░░██║╚██████╔╝██████╔╝
     ░╚════╝░╚══════╝╚═╝░░╚═╝╚══════╝╚═════╝░╚═╝░░╚═╝░╚═════╝░╚═════╝░

     ─────╮    ╭──╮         ╭──╮    ╭──╮         ╭──╮    ╭─────
          │    │  │         │  │    │  │         │  │    │
     ─────╯────╯  ╰─────────╯  ╰────╯  ╰─────────╯  ╰────╯─────

              ██████╗░██╗░░░██╗██╗░░░░░░██████╗███████╗
              ██╔══██╗██║░░░██║██║░░░░░██╔════╝██╔════╝
              ██████╔╝██║░░░██║██║░░░░░╚█████╗░█████╗░░
              ██╔═══╝░██║░░░██║██║░░░░░░╚═══██╗██╔══╝░░
              ██║░░░░░╚██████╔╝███████╗██████╔╝███████╗
              ╚═╝░░░░░░╚═════╝░╚══════╝╚═════╝░╚══════╝

          crypto intelligence for AI agents · x402 micropayments
```

# Cerebrus Pulse Python SDK

[![PyPI](https://img.shields.io/pypi/v/cerebrus-pulse)](https://pypi.org/project/cerebrus-pulse/) [![Downloads](https://img.shields.io/pypi/dm/cerebrus-pulse)](https://pypi.org/project/cerebrus-pulse/) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

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
# Technical analysis — $0.025 USDC
pulse = client.pulse("BTC", timeframes="1h,4h")
print(f"Price: ${pulse.price}")
print(f"RSI (1h): {pulse.timeframes['1h'].indicators.rsi_14}")
print(f"Trend: {pulse.timeframes['1h'].indicators.trend.label}")
print(f"Confluence: {pulse.confluence.score} ({pulse.confluence.bias})")

# Liquidation heatmap — $0.03 USDC
liq = client.liquidations("BTC")
print(f"Cascade risk: {liq.summary.cascade_risk}")
print(f"Nearest cluster: {liq.summary.nearest_cluster}")
for zone in liq.long_zones[:3]:
    print(f"  Long liq at ${zone.price} ({zone.leverage}) — ${zone.estimated_liq_usd:,}")

# Market stress index — $0.015 USDC
stress = client.stress()
print(f"Stress: {stress.stress_index.level} ({stress.stress_index.score:.2f})")

# CEX-DEX divergence — $0.02 USDC
div = client.cex_dex("ETH")
print(f"ETH divergence: {div.divergence.spread_bps} bps ({div.divergence.direction})")

# Chainlink basis — $0.02 USDC
basis = client.basis("BTC")
print(f"BTC basis: {basis.basis.basis_bps} bps — {basis.basis.signal}")

# USDC depeg monitor — $0.01 USDC
depeg = client.depeg()
print(f"USDC: {depeg.usdc.peg_status} ({depeg.usdc.deviation_bps} bps)")

# Sentiment — $0.01 USDC
sentiment = client.sentiment()
print(f"Market: {sentiment.overall} (score: {sentiment.score})")

# Funding rates — $0.01 USDC
funding = client.funding("ETH", lookback_hours=48)
print(f"ETH funding: {funding.annualized_pct}% annualized")

# Screener — $0.06 USDC
screen = client.screener(top_n=10)
for coin in screen.results:
    print(f"{coin.coin}: RSI={coin.rsi_14}, trend={coin.trend}")

# Bundle (all data, 9% discount) — $0.05 USDC
bundle = client.bundle("SOL")
print(f"SOL price: ${bundle.pulse.price}")
```

## Response Models

All paid endpoints return typed dataclass objects:

- `PulseResponse` — Technical indicators, derivatives, regime, confluence
- `LiquidationsResponse` — Long/short liquidation zones, cascade risk, nearest cluster
- `StressResponse` — Market stress index with level, score, and scan statistics
- `CexDexResponse` — CEX-DEX divergence with spread bps and direction
- `BasisResponse` — Chainlink basis with signal and interpretation
- `DepegResponse` — USDC peg status, deviation, infrastructure health
- `SentimentResponse` — Overall sentiment, fear/greed, momentum, funding bias
- `FundingResponse` — Current rate, historical stats, rate history
- `OIResponse` — Open interest delta, percentile, trend, divergence
- `SpreadResponse` — Bid-ask spread, slippage estimates, liquidity score
- `CorrelationResponse` — BTC-alt correlation matrix, regime, sector averages
- `ScreenerResponse` — Multi-coin scan with signals and confluence
- `BundleResponse` — Pulse + sentiment + funding combined

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
- [MCP Server](https://github.com/0xsl1m/cerebrus-pulse-mcp) — Use with Claude Desktop, Cursor, etc.
- [LangChain Tools](https://github.com/0xsl1m/langchain-cerebrus-pulse)

## Disclaimer

Cerebrus Pulse provides market data and technical indicators for **informational purposes only**. Nothing provided by this SDK or the underlying API constitutes financial advice, investment advice, or trading advice. AI-generated analysis, signals, and sentiment labels are algorithmic outputs — not recommendations to buy, sell, or hold any asset. Cryptocurrency trading involves substantial risk of loss. You are solely responsible for your own trading decisions.

## License

MIT
