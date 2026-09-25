"""x402 payment support for the Cerebrus Pulse SDK.

Reading payment terms from a 402 needs nothing beyond the core SDK. Paying
needs the optional extras:

    pip install "cerebrus-pulse[pay]"        # USDC on Base
    pip install "cerebrus-pulse[pay,svm]"    # plus USDC on Solana

Payments are made with the official x402 client (``x402ClientSync``) as x402
v2 payments, sent in the ``PAYMENT-SIGNATURE`` header. The API ignores the v1
``X-PAYMENT`` header, so v1 terms are never paid.

Every payment is checked by a :class:`SpendGuard` before it is signed:

* ``max_payment_usd`` caps one payment (env ``CEREBRUS_MAX_PAYMENT_USD``,
  default $0.10; the most expensive endpoint costs $0.06).
* ``max_spend_usd`` caps the total one client signs (env
  ``CEREBRUS_MAX_SPEND_USD``, default $1.00). Every signed payment counts,
  even one the API then rejects: a signed authorization can still settle.
  Paid calls on one client run one at a time, so the cap holds across threads.
* Only USDC is paid, and only to an allowlisted payTo: on Base, env
  ``CEREBRUS_ALLOWED_PAYTO`` (default :data:`DEFAULT_ALLOWED_PAYTO`); on
  Solana, env ``CEREBRUS_ALLOWED_PAYTO_SOLANA`` (default: none, so Solana is
  never paid until you set it).
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable

# The published Base payTo of api.cerebruspulse.xyz. Auto-pay refuses any other
# payee unless CEREBRUS_ALLOWED_PAYTO (or allowed_pay_to=) says otherwise.
# This default MUST be updated whenever the gateway's payTo address is rotated.
DEFAULT_ALLOWED_PAYTO = "0x62b2c8ec710FD40A0139e22605D472e3767fd8f6"
# No Solana payee is trusted by default: set CEREBRUS_ALLOWED_PAYTO_SOLANA (or
# allowed_pay_to_solana=) to the Solana payTo the API quotes to enable it.
DEFAULT_ALLOWED_PAYTO_SOLANA = ""
DEFAULT_MAX_PAYMENT_USD = "0.10"
DEFAULT_MAX_SPEND_USD = "1.00"

BASE_NETWORK = "eip155:8453"
BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
SOLANA_NETWORK = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"
SOLANA_USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"

_USDC_UNIT = Decimal(1_000_000)  # USDC has 6 decimals on Base and Solana
_USDC_BY_NETWORK = {BASE_NETWORK: BASE_USDC.lower(), SOLANA_NETWORK: SOLANA_USDC}
_EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_SOLANA_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

PAY_EXTRA_HINT = 'pip install "cerebrus-pulse[pay]"'
SVM_EXTRA_HINT = 'pip install "cerebrus-pulse[pay,svm]"'


# ── Payment terms (no x402 dependency) ─────────────────────────────────────


@dataclass(frozen=True)
class PaymentTerms:
    """One payment option offered by a 402 response."""

    scheme: str
    network: str
    asset: str
    pay_to: str
    amount: str  # atomic units, as the API sent it
    price_usd: Decimal | None  # set when the asset is USDC on a known network
    x402_version: int


def _usdc_price(network: str, asset: str, amount: str) -> Decimal | None:
    usdc = _USDC_BY_NETWORK.get(network)
    if usdc is None or not (amount.isascii() and amount.isdigit()):
        return None
    if asset != usdc and asset.lower() != usdc:
        return None
    return Decimal(int(amount)) / _USDC_UNIT


def parse_payment_terms(response: Any) -> list[PaymentTerms]:
    """Read the payment options from a 402 response.

    The API sends x402 v2 terms in the base64 ``PAYMENT-REQUIRED`` header and
    an informational v1-shaped JSON body. The header wins; the body is a
    fallback. A malformed 402 yields an empty list, never an exception.
    """
    offers: list = []
    version = 2
    header = response.headers.get(PAYMENT_REQUIRED_HEADER)
    if header:
        try:
            offers = json.loads(base64.b64decode(header)).get("accepts") or []
        except (ValueError, TypeError, AttributeError):
            offers = []
    if not offers:
        version = 1
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("x402Version") == 1:
                offers = body.get("accepts") or []
        except ValueError:
            offers = []

    terms = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        network = str(offer.get("network", ""))
        if version == 1 and network == "base":
            network = BASE_NETWORK
        asset = str(offer.get("asset", ""))
        amount = str(offer.get("amount") if version == 2 else offer.get("maxAmountRequired"))
        terms.append(PaymentTerms(
            scheme=str(offer.get("scheme", "")),
            network=network,
            asset=asset,
            pay_to=str(offer.get("payTo", "")),
            amount=amount,
            price_usd=_usdc_price(network, asset, amount),
            x402_version=version,
        ))
    return terms


# ── Spend limits ────────────────────────────────────────────────────────────


def _usd(name: str, value: Any, default: str) -> Decimal:
    if value is None:
        value = os.environ.get(name, "").strip() or default
    raw = str(value).strip()
    try:
        amount = Decimal(raw.lstrip("$"))
    except InvalidOperation:
        raise ValueError(f"{name}={raw!r} is not a USD amount") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{name}={raw!r} must be a non-negative USD amount")
    return amount


def _addresses(name: str, value: Any, default: str, pattern: re.Pattern) -> list[str]:
    if value is None:
        value = os.environ.get(name, "").strip() or default
    items: Iterable = value.split(",") if isinstance(value, str) else value
    addresses = [str(a).strip() for a in items if str(a).strip()]
    bad = [a for a in addresses if not pattern.match(a)]
    if bad:
        raise ValueError(f"{name} has invalid address(es): {bad!r}")
    return addresses


class SpendGuard:
    """Client-side limits, checked before any payment is signed.

    Only x402 v2 payments of USDC, to an allowlisted payTo, are made. No single
    payment may exceed ``max_payment_usd``, and the total signed through this
    guard may not exceed ``max_spend_usd``. Every signed payment counts toward
    the budget, even one the API then rejects.
    """

    def __init__(self, max_payment_usd: Decimal, max_spend_usd: Decimal,
                 allowed_pay_to: Iterable[str], allowed_pay_to_solana: Iterable[str] = ()):
        self.max_payment_usd = max_payment_usd
        self.max_spend_usd = max_spend_usd
        self.allowed_pay_to = frozenset(a.lower() for a in allowed_pay_to)
        self.allowed_pay_to_solana = frozenset(allowed_pay_to_solana)  # base58 is case-sensitive
        self.spent_usd = Decimal(0)
        self.last_refusal: str | None = None

    @classmethod
    def from_settings(cls, max_payment_usd: Any = None, max_spend_usd: Any = None,
                      allowed_pay_to: Any = None, allowed_pay_to_solana: Any = None) -> SpendGuard:
        """Build a guard from explicit values, else the environment, else the defaults.

        Raises ValueError on a malformed setting, so a typo never lifts a limit.
        """
        return cls(
            _usd("CEREBRUS_MAX_PAYMENT_USD", max_payment_usd, DEFAULT_MAX_PAYMENT_USD),
            _usd("CEREBRUS_MAX_SPEND_USD", max_spend_usd, DEFAULT_MAX_SPEND_USD),
            _addresses("CEREBRUS_ALLOWED_PAYTO", allowed_pay_to,
                       DEFAULT_ALLOWED_PAYTO, _EVM_ADDRESS_RE),
            _addresses("CEREBRUS_ALLOWED_PAYTO_SOLANA", allowed_pay_to_solana,
                       DEFAULT_ALLOWED_PAYTO_SOLANA, _SOLANA_ADDRESS_RE),
        )

    def refusal(self, requirement: Any, x402_version: int = 2) -> str | None:
        """Why this offer must not be paid, or None if it is within every limit."""
        network, asset = str(requirement.network), str(requirement.asset)
        pay_to = str(requirement.pay_to)
        if x402_version != 2:
            return "only x402 v2 payments are sent (the API ignores v1 X-PAYMENT)"
        if network == BASE_NETWORK and asset.lower() == BASE_USDC.lower():
            if pay_to.lower() not in self.allowed_pay_to:
                return f"payTo {pay_to} is not in CEREBRUS_ALLOWED_PAYTO"
        elif network == SOLANA_NETWORK and asset == SOLANA_USDC:
            if pay_to not in self.allowed_pay_to_solana:
                return f"Solana payTo {pay_to} is not in CEREBRUS_ALLOWED_PAYTO_SOLANA"
        else:
            return f"only USDC on Base or Solana is paid (offer: asset {asset} on {network})"
        amount = str(requirement.get_amount())
        if not (amount.isascii() and amount.isdigit()):
            return f"unreadable amount {amount!r}"
        price = Decimal(int(amount)) / _USDC_UNIT
        if price > self.max_payment_usd:
            return f"price ${price} exceeds CEREBRUS_MAX_PAYMENT_USD (${self.max_payment_usd})"
        if self.spent_usd + price > self.max_spend_usd:
            return (
                f"budget reached: ${self.spent_usd} already signed by this client and this "
                f"call costs ${price}, over CEREBRUS_MAX_SPEND_USD (${self.max_spend_usd})"
            )
        return None

    def policy(self, x402_version: int, requirements: list) -> list:
        """x402 PaymentPolicy: keep only the offers inside every limit."""
        kept, reasons = [], []
        for requirement in requirements:
            reason = self.refusal(requirement, x402_version)
            if reason is None:
                kept.append(requirement)
            else:
                reasons.append(reason)
        if not kept:
            self.last_refusal = "; ".join(reasons) or "no payable offer"
        return kept

    def record(self, context: Any) -> None:
        """x402 after-payment-creation hook: count every signed payment."""
        amount = int(context.selected_requirements.get_amount())
        self.spent_usd += Decimal(amount) / _USDC_UNIT


# ── Paying (needs the [pay] extra) ──────────────────────────────────────────


def build_payment_client(guard: SpendGuard, wallet_key: str | None = None,
                         solana_key: str | None = None, x402_client: Any = None) -> Any:
    """An ``x402ClientSync`` that pays inside ``guard``.

    With ``x402_client`` the guard is added to that client (its own schemes and
    spend controls are kept). Otherwise a client is built for the given Base
    and/or Solana key. The keys are handed to the x402 signers and not stored.
    """
    try:
        from x402 import x402ClientSync
    except ImportError as e:
        raise ImportError(f"x402 payments need the pay extra: {PAY_EXTRA_HINT} ({e})") from None

    if x402_client is not None:
        if wallet_key or solana_key:
            raise ValueError("pass either x402_client or a wallet key, not both")
        client = x402_client
    else:
        client = x402ClientSync()
        # SDK-level backstop for the per-call cap; it also limits payment to the
        # SDK's recognized stablecoins.
        client.set_spend_controls({"max_amount_per_payment": f"${guard.max_payment_usd}"})
        if wallet_key:
            try:
                from eth_account import Account
                from x402.mechanisms.evm.exact import register_exact_evm_client
            except ImportError as e:
                raise ImportError(
                    f"Base payments need the pay extra: {PAY_EXTRA_HINT} ({e})") from None
            try:
                account = Account.from_key(wallet_key)
            except Exception:  # noqa: BLE001 - never echo the key
                raise ValueError("wallet_key is not a valid EVM private key") from None
            register_exact_evm_client(client, account, networks=BASE_NETWORK)
        if solana_key:
            try:
                from x402.mechanisms.svm import KeypairSigner
                from x402.mechanisms.svm.exact import register_exact_svm_client
            except ImportError as e:
                raise ImportError(
                    f"Solana payments need the svm extra: {SVM_EXTRA_HINT} ({e})") from None
            try:
                signer = KeypairSigner.from_base58(solana_key)
            except Exception:  # noqa: BLE001 - never echo the key
                raise ValueError("solana_key is not a valid base58 Solana keypair") from None
            register_exact_svm_client(client, signer, networks=SOLANA_NETWORK)

    client.register_policy(guard.policy)
    client.on_after_payment_creation(guard.record)
    return client


class Payer:
    """Settles a 402 with the x402 client's own round trip, over the SDK's httpx client.

    One payment at a time: the guard's budget check (x402 policy) and its count
    of the signed amount (after-creation hook) happen inside one round trip, so
    concurrent round trips could all pass the check before any is counted.
    """

    def __init__(self, x402_client: Any, guard: SpendGuard):
        from x402.http import PaymentRoundTripper, x402HTTPClientSync

        self.guard = guard
        self._round_tripper = PaymentRoundTripper(x402HTTPClientSync(x402_client))
        self._count = 0
        self._lock = threading.Lock()

    def pay(self, response: Any, retry: Callable[[dict[str, str]], Any]) -> Any:
        """Pay the 402 ``response`` and return the API's answer to the paid retry.

        ``retry(headers)`` must resend the original request with extra headers.
        Raises PaymentRefused if nothing could be signed within the limits.
        """
        with self._lock:
            self.guard.last_refusal = None
            self._count += 1
            try:
                return self._round_tripper.handle_response(
                    request_id=f"cerebrus-pulse-{id(self)}-{self._count}",
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                    retry_func=retry,
                    request_url=str(response.request.url),
                )
            except Exception as e:  # noqa: BLE001
                raise PaymentRefused(self._local_refusal(e), e) from e

    def _local_refusal(self, exc: BaseException) -> str | None:
        """The reason a payment was refused before signing, else None."""
        if self.guard.last_refusal:
            return self.guard.last_refusal
        try:
            from x402 import NoMatchingRequirementsError
        except ImportError:
            return None
        if isinstance(exc, NoMatchingRequirementsError):
            return str(exc)
        return None


class PaymentRefused(Exception):
    """Internal: the x402 flow stopped before a paid retry was answered."""

    def __init__(self, reason: str | None, error: BaseException):
        self.reason = reason  # set when a limit refused the payment (nothing signed)
        self.error = error
        super().__init__(reason or str(error))
