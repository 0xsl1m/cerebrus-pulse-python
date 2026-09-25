
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

Python SDK for [Cerebrus Pulse](https://cerebruspulse.xyz) — real-time crypto intelligence API for 50+ Hyperliquid perpetuals. Paid endpoints cost a few cents per call in USDC, paid over [x402](https://x402.org): no API keys, no subscriptions.

## Install

```bash
pip install cerebrus-pulse              # free endpoints; paid ones raise PaymentRequired with the price
pip install "cerebrus-pulse[pay]"       # + automatic payment in USDC on Base
pip install "cerebrus-pulse[pay,svm]"   # + automatic payment in USDC on Solana
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

## Paying for Endpoints (x402)

Install the `pay` extra and give the client the private key of a **dedicated, low-balance** Base wallet holding a little USDC. When an endpoint answers `402 Payment Required`, the SDK signs an x402 v2 payment with the official [x402 client](https://pypi.org/project/x402/), resends the request with it in the `PAYMENT-SIGNATURE` header, and returns the data. The wallet needs USDC only: x402 payments are gasless for the payer.

```python
import os
from cerebrus_pulse import CerebrusPulse

client = CerebrusPulse(wallet_key=os.environ["CEREBRUS_WALLET_KEY"])

pulse = client.pulse("BTC", timeframes="1h,4h")
print(f"Confluence: {pulse.confluence.score} ({pulse.confluence.bias})")
print(f"Spent by this client: ${client.spent_usd}")
```

Never paste a key into code, and never use a wallet that holds more than you are willing to spend. You can also pass your own configured `x402.x402ClientSync` as `x402_client=` instead of a key.

### Spend limits

Every payment is checked before it is signed. A refused payment raises `PaymentBlocked` and nothing is signed.

| Setting (argument / environment variable) | Default | Meaning |
|---|---|---|
| `max_payment_usd` / `CEREBRUS_MAX_PAYMENT_USD` | `0.10` | Most one call may cost. The priciest endpoint is $0.06. |
| `max_spend_usd` / `CEREBRUS_MAX_SPEND_USD` | `1.00` | Total one client may sign. Every signed payment counts, even one the API rejects. |
| `allowed_pay_to` / `CEREBRUS_ALLOWED_PAYTO` | `0x62b2c8ec710FD40A0139e22605D472e3767fd8f6` | Base addresses the SDK will pay (comma-separated). The default is the API's published Base payTo. If the API ever changes it, payments are refused until you upgrade the SDK or set this. |
| `allowed_pay_to_solana` / `CEREBRUS_ALLOWED_PAYTO_SOLANA` | none | Solana addresses the SDK will pay. Empty means Solana is never paid. |

Arguments win over environment variables. Only USDC is paid, only x402 v2 terms are paid, and a malformed setting raises `ValueError` instead of lifting a limit.

One client is safe to share between threads (LangChain runs parallel tool calls in threads, for example). Its paid calls then settle one at a time, so the limits hold.

### Solana

```bash
pip install "cerebrus-pulse[pay,svm]"
```

```python
client = CerebrusPulse(
    solana_key=os.environ["CEREBRUS_SOLANA_KEY"],            # base58 keypair
    allowed_pay_to_solana="<the Solana payTo in the API's 402 terms>",
)
```

Solana is off until you allowlist the payee. The `svm` extra pins `solana<0.37`: solana 0.40 removed a module the x402 Solana client imports.

### Without a wallet

Paid endpoints raise `PaymentRequired`, which carries the terms from the 402:

```python
from cerebrus_pulse import CerebrusPulse, PaymentRequired

try:
    CerebrusPulse().pulse("BTC")
except PaymentRequired as e:
    term = e.terms[0]
    print(f"Costs ${e.price_usd} USDC, paid to {term.pay_to} on {term.network}")
```

## Endpoints

```python
# Technical analysis
pulse = client.pulse("BTC", timeframes="1h,4h")  # 5m, 15m, 1h, 4h, 1d, 1w
print(f"Price: ${pulse.price}")
print(f"RSI (1h): {pulse.timeframes['1h'].indicators.rsi_14}")
print(f"Trend: {pulse.timeframes['1h'].indicators.trend.label}")
print(f"Confluence: {pulse.confluence.score} ({pulse.confluence.bias})")

# Liquidation heatmap
liq = client.liquidations("BTC")
print(f"Cascade risk: {liq.summary.cascade_risk}")
print(f"Nearest cluster: {liq.summary.nearest_cluster}")
for zone in liq.long_zones[:3]:
    print(f"  Long liq at ${zone.price} ({zone.leverage}) — ${zone.estimated_liq_usd:,}")

# Market stress index
stress = client.stress()
print(f"Stress: {stress.stress_index.level} ({stress.stress_index.score:.2f})")

# CEX-DEX divergence
div = client.cex_dex("ETH")
print(f"ETH divergence: {div.divergence.spread_bps} bps ({div.divergence.direction})")

# Chainlink basis
basis = client.basis("BTC")
print(f"BTC basis: {basis.basis.basis_bps} bps — {basis.basis.signal}")

# USDC depeg monitor
depeg = client.depeg()
print(f"USDC: {depeg.usdc.peg_status} ({depeg.usdc.deviation_bps} bps)")

# Sentiment (a bucketed label: very_bearish … very_bullish)
sentiment = client.sentiment()
print(f"Market: {sentiment.label}")

# Funding rates
funding = client.funding("ETH", lookback_hours=48)
print(f"ETH funding: {funding.current_rate} now, {funding.annualized_pct}% annualized")

# Screener
screen = client.screener(top_n=10)  # 1-50
for coin in screen.results:
    print(f"{coin.coin}: RSI={coin.rsi_14}, trend={coin.trend}")

# Bundle: pulse, sentiment and funding in one call
bundle = client.bundle("SOL")
print(f"SOL price: ${bundle.pulse.price}")
```

## Prices

Indicative per-call prices in USDC, as the API published them on 2026-09-24 (also exported as `INDICATIVE_PRICES_USD`). The API sets the price: the 402 terms say what is charged, and `max_payment_usd` caps what the SDK will pay.

| Method | Endpoint | Price |
|---|---|---|
| `health()`, `coins()` | `/health`, `/coins` | Free |
| `pulse()` | `/pulse/{coin}` | $0.025 |
| `sentiment()` | `/sentiment` | $0.01 |
| `funding()` | `/funding/{coin}` | $0.01 |
| `bundle()` | `/bundle/{coin}` | $0.05 |
| `screener()` | `/screener` | $0.06 |
| `oi()` | `/oi/{coin}` | $0.015 |
| `spread()` | `/spread/{coin}` | $0.015 |
| `correlation()` | `/correlation` | $0.05 |
| `stress()` | `/arb` | $0.02 |
| `cex_dex()` | `/cex-dex/{token}` | $0.02 |
| `basis()` | `/basis/{coin}` | $0.02 |
| `depeg()` | `/depeg` | $0.01 |
| `liquidations()` | `/liquidations/{coin}` | $0.03 |

## Response Models

All paid endpoints return typed dataclass objects that follow what the API actually returns. A field the response lacks is `None`, never a made-up `0`:

- `PulseResponse` — Technical indicators, derivatives, regime, confluence
- `LiquidationsResponse` — Long/short liquidation zones, cascade risk, nearest cluster
- `StressResponse` — Market stress index with level, score, and scan statistics
- `CexDexResponse` — CEX-DEX divergence with spread bps and direction
- `BasisResponse` — Chainlink basis with signal and interpretation
- `DepegResponse` — USDC peg status, deviation, infrastructure health
- `SentimentResponse` — Bucketed market sentiment label (`very_bearish` … `very_bullish`) and its timestamp
- `FundingResponse` — Current, average, min and max funding rate, annualized %, sample count
- `OIResponse` — Open interest delta, percentile, trend, divergence
- `SpreadResponse` — Bid-ask spread, slippage estimates, liquidity score
- `CorrelationResponse` — BTC-alt correlation matrix, regime, sector averages
- `ScreenerResponse` — Multi-coin scan with signals and confluence
- `BundleResponse` — Pulse + sentiment + funding combined

Access raw JSON via the `.raw` attribute on any response. Upgrading from 0.3.x? `FundingResponse` and `SentimentResponse` changed shape; see [CHANGELOG.md](CHANGELOG.md).

## Error Handling

```python
from cerebrus_pulse import (
    CerebrusPulse, CerebrusPulseError, PaymentBlocked, PaymentRejected,
    PaymentRequired, RateLimited,
)

try:
    pulse = client.pulse("BTC")
except PaymentBlocked as e:
    print(f"Refused by the spend limits, nothing signed: {e.reason}")
except PaymentRejected:
    print("Paid, but the API did not accept the payment. Check the wallet's USDC.")
except PaymentRequired as e:
    print(f"Payment needed: ${e.price_usd} USDC")
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
