# Changelog

## 0.4.0 (unreleased)

### Added
- Automatic x402 payment. `pip install "cerebrus-pulse[pay]"` and pass
  `wallet_key=` (USDC on Base), or `[pay,svm]` and `solana_key=` (USDC on
  Solana), or your own `x402_client=`. Payments are x402 v2, sent in the
  `PAYMENT-SIGNATURE` header.
- Spend limits checked before anything is signed: `max_payment_usd` /
  `CEREBRUS_MAX_PAYMENT_USD` (default $0.10), `max_spend_usd` /
  `CEREBRUS_MAX_SPEND_USD` (default $1.00), and payee allowlists
  `allowed_pay_to` / `CEREBRUS_ALLOWED_PAYTO` (default: the API's published
  Base payTo) and `allowed_pay_to_solana` / `CEREBRUS_ALLOWED_PAYTO_SOLANA`
  (default: none). The limits hold when one client is used from many
  threads: its paid calls settle one at a time.
- `PaymentRequired` carries the 402 terms (`.terms`, `.price_usd`), with the
  subclasses `PaymentBlocked`, `PaymentRejected` and `PaymentFailed`.
- `client.can_pay`, `client.spent_usd`, and `INDICATIVE_PRICES_USD`.

### Changed (breaking)
- `FundingResponse` follows the API's flat `/funding` response. It keeps
  `current_rate`, `average_rate`, `min_rate`, `max_rate`, `annualized_pct` and
  `lookback_hours`, adds `records` and `positive_pct`, and drops `history` and
  `timestamp_iso`, which the API never sent. Before, every field read 0.
- `SentimentResponse` is now `label` and `as_of`. `score`, `fear_greed`,
  `momentum`, `funding_bias` and `timestamp_iso` are gone: the API publishes a
  bucketed label only. `overall` remains as an alias of `label`.
- Missing fields in these models are `None` instead of `0` or `"unknown"`.

### Fixed
- The User-Agent reports the real version instead of `0.1.0`.
- Docstring and README prices match the API (`stress()` is $0.02), no bundle
  discount is claimed, and the documented timeframes (5m to 1w) and screener
  range (1-50) match the API.
