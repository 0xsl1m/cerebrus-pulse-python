"""x402 payment through the SDK (F026).

HTTP is mocked with httpx.MockTransport; payments are signed locally by the
real x402 client with an obviously fake, never-funded key. Nothing touches
the network and no payment can settle.
"""

import base64
import json
import sys
import threading
import time
from decimal import Decimal

import httpx
import pytest

pytest.importorskip("x402")

from x402.http import encode_payment_required_header  # noqa: E402
from x402.schemas import PaymentRequired as X402PaymentRequired  # noqa: E402
from x402.schemas import PaymentRequirements, ResourceInfo  # noqa: E402

from cerebrus_pulse import (  # noqa: E402
    CerebrusPulse,
    PaymentBlocked,
    PaymentFailed,
    PaymentRejected,
    PaymentRequired,
    SpendGuard,
)
from cerebrus_pulse import payment  # noqa: E402
from cerebrus_pulse.models import PulseResponse  # noqa: E402

# A syntactically valid, obviously fake secp256k1 key. Never funded.
DUMMY_KEY = "0x" + "11" * 32
PAY_TO = payment.DEFAULT_ALLOWED_PAYTO
OTHER_PAY_TO = "0x000000000000000000000000000000000000dEaD"
BASE_USDC = payment.BASE_USDC
SOLANA_PAY_TO = "CerebrusTestPayee111111111111111111111111111"  # made up, valid base58
LIMIT_VARS = ("CEREBRUS_MAX_PAYMENT_USD", "CEREBRUS_MAX_SPEND_USD",
              "CEREBRUS_ALLOWED_PAYTO", "CEREBRUS_ALLOWED_PAYTO_SOLANA")
PULSE = {"coin": "BTC", "price": {"current": 84512.5}, "timeframes": {},
         "confluence": {"score": 0.62, "bias": "bullish"}}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in LIMIT_VARS:
        monkeypatch.delenv(name, raising=False)


def _atomic(usd: str) -> str:
    return str(int(Decimal(usd) * 1_000_000))


def offer(usd="0.025", pay_to=PAY_TO, network="eip155:8453", asset=BASE_USDC):
    return PaymentRequirements(
        scheme="exact", network=network, asset=asset, amount=_atomic(usd),
        pay_to=pay_to, max_timeout_seconds=300,
        extra={"name": "USD Coin", "version": "2"},
    )


def gateway_402(url, *offers, v2=True, v1_body=True):
    """A 402 shaped like the gateway's: v2 terms in PAYMENT-REQUIRED, v1 body."""
    offers = offers or (offer(),)
    headers = {}
    if v2:
        required = X402PaymentRequired(x402_version=2, accepts=list(offers),
                                       resource=ResourceInfo(url=str(url)))
        headers["PAYMENT-REQUIRED"] = encode_payment_required_header(required)
    body = {}
    if v1_body:
        first = offers[0]
        body = {"x402Version": 1, "error": "Payment required", "accepts": [{
            "scheme": "exact", "network": "base", "maxAmountRequired": first.amount,
            "resource": str(url), "description": "", "mimeType": "application/json",
            "payTo": first.pay_to, "maxTimeoutSeconds": 300, "asset": first.asset,
            "extra": {"name": "USD Coin", "version": "2"},
        }]}
    return httpx.Response(402, json=body, headers=headers)


class FakeAPI:
    """Mock transport: unpaid requests get a 402, paid ones get ``paid``."""

    def __init__(self, unpaid=None, paid=None):
        self.requests: list[httpx.Request] = []
        self.unpaid = unpaid or (lambda req: gateway_402(req.url))
        self.paid = paid or (lambda req: httpx.Response(200, json=PULSE))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("PAYMENT-SIGNATURE") or request.headers.get("X-PAYMENT"):
            return self.paid(request)
        return self.unpaid(request)

    @property
    def paid_flags(self):
        return [bool(r.headers.get("PAYMENT-SIGNATURE") or r.headers.get("X-PAYMENT"))
                for r in self.requests]


def make_client(api: FakeAPI, **kwargs) -> CerebrusPulse:
    client = CerebrusPulse(**kwargs)
    client._transport = httpx.MockTransport(api)
    return client


# ── Unpaid: 402 terms are surfaced ──────────────────────────────────────────

def test_without_wallet_a_402_raises_payment_required_with_terms():
    api = FakeAPI()
    client = make_client(api)
    assert not client.can_pay

    with pytest.raises(PaymentRequired) as exc:
        client.pulse("BTC")

    err = exc.value
    assert type(err) is PaymentRequired
    assert err.status_code == 402
    assert err.price_usd == Decimal("0.025")
    assert err.terms[0].pay_to == PAY_TO
    assert err.terms[0].network == "eip155:8453"
    assert err.terms[0].x402_version == 2
    assert "cerebrus-pulse[pay]" in err.detail
    assert api.paid_flags == [False]


def test_terms_fall_back_to_the_v1_body():
    api = FakeAPI(unpaid=lambda req: gateway_402(req.url, offer("0.06"), v2=False))
    with pytest.raises(PaymentRequired) as exc:
        make_client(api).screener()
    assert exc.value.price_usd == Decimal("0.06")
    assert exc.value.terms[0].network == "eip155:8453"
    assert exc.value.terms[0].x402_version == 1


def test_malformed_402_still_raises_payment_required():
    api = FakeAPI(unpaid=lambda req: httpx.Response(
        402, headers={"PAYMENT-REQUIRED": "%%%not-base64"}, text="nope"))
    with pytest.raises(PaymentRequired) as exc:
        make_client(api).pulse("BTC")
    assert exc.value.terms == []
    assert exc.value.price_usd is None


# ── Paying ──────────────────────────────────────────────────────────────────

def test_pays_with_a_v2_payment_signature_and_returns_data():
    api = FakeAPI()
    client = make_client(api, wallet_key=DUMMY_KEY)
    assert client.can_pay

    pulse = client.pulse("BTC")

    assert isinstance(pulse, PulseResponse)
    assert pulse.price == 84512.5
    assert api.paid_flags == [False, True]
    paid = api.requests[1]
    assert "X-PAYMENT" not in paid.headers  # the API only reads PAYMENT-SIGNATURE
    signed = json.loads(base64.b64decode(paid.headers["PAYMENT-SIGNATURE"]))
    assert signed["x402Version"] == 2
    assert signed["accepted"]["payTo"] == PAY_TO
    assert signed["accepted"]["amount"] == "25000"
    assert signed["accepted"]["network"] == "eip155:8453"
    assert paid.url.path == "/pulse/BTC"
    assert paid.url.params["timeframes"] == "1h,4h"
    assert client.spent_usd == Decimal("0.025")


def test_free_endpoints_are_never_paid():
    api = FakeAPI(unpaid=lambda req: httpx.Response(200, json={"coins": ["BTC"]}))
    client = make_client(api, wallet_key=DUMMY_KEY)
    assert client.coins() == ["BTC"]
    assert api.paid_flags == [False]
    assert client.spent_usd == 0


def test_mixed_offers_pay_the_base_offer_when_solana_is_not_configured():
    api = FakeAPI(unpaid=lambda req: gateway_402(
        req.url,
        offer(pay_to=PAY_TO),
        offer(network=payment.SOLANA_NETWORK, asset=payment.SOLANA_USDC, pay_to=SOLANA_PAY_TO),
    ))
    client = make_client(api, wallet_key=DUMMY_KEY)
    client.pulse("BTC")
    signed = json.loads(base64.b64decode(api.requests[1].headers["PAYMENT-SIGNATURE"]))
    assert signed["accepted"]["network"] == "eip155:8453"


# ── Spend limits ────────────────────────────────────────────────────────────

def test_unknown_payto_is_blocked_before_signing():
    api = FakeAPI(unpaid=lambda req: gateway_402(req.url, offer(pay_to=OTHER_PAY_TO)))
    client = make_client(api, wallet_key=DUMMY_KEY)

    with pytest.raises(PaymentBlocked) as exc:
        client.pulse("BTC")

    assert "CEREBRUS_ALLOWED_PAYTO" in exc.value.reason
    assert exc.value.terms[0].pay_to == OTHER_PAY_TO
    assert isinstance(exc.value, PaymentRequired)  # old `except PaymentRequired` still works
    assert api.paid_flags == [False]
    assert client.spent_usd == 0


def test_per_call_cap_blocks_an_expensive_payment():
    api = FakeAPI(unpaid=lambda req: gateway_402(req.url, offer("0.06")))
    client = make_client(api, wallet_key=DUMMY_KEY, max_payment_usd="0.05")
    with pytest.raises(PaymentBlocked):
        client.screener()
    assert api.paid_flags == [False]
    assert client.spent_usd == 0


def test_per_call_cap_can_be_raised_above_the_x402_default(monkeypatch):
    # x402's own default cap is $1 per payment; the SDK setting must win.
    monkeypatch.setenv("CEREBRUS_MAX_PAYMENT_USD", "2")
    monkeypatch.setenv("CEREBRUS_MAX_SPEND_USD", "5")
    api = FakeAPI(unpaid=lambda req: gateway_402(req.url, offer("1.50")))
    client = make_client(api, wallet_key=DUMMY_KEY)
    client.pulse("BTC")
    assert client.spent_usd == Decimal("1.50")


def test_budget_stops_signing_once_reached():
    api = FakeAPI()
    client = make_client(api, wallet_key=DUMMY_KEY, max_spend_usd="0.05")
    client.pulse("BTC")
    client.pulse("BTC")
    assert client.spent_usd == Decimal("0.05")

    with pytest.raises(PaymentBlocked) as exc:
        client.pulse("BTC")

    assert "CEREBRUS_MAX_SPEND_USD" in exc.value.reason
    assert client.spent_usd == Decimal("0.05")
    assert api.paid_flags == [False, True, False, True, False]


def _concurrent_pulses(client, n):
    """Run ``n`` client.pulse() calls in threads; return (results, errors)."""
    results, errors = [], []

    def call():
        try:
            results.append(client.pulse("BTC"))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=call) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads)
    return results, errors


def test_budget_holds_when_one_client_pays_from_many_threads(monkeypatch):
    # All eight 402s arrive together, and each check is slowed so that, without
    # a lock, every thread passes the budget check before any payment is counted.
    barrier = threading.Barrier(8, timeout=10)

    def unpaid(req):
        barrier.wait()
        return gateway_402(req.url, offer("0.06"))

    real_policy = SpendGuard.policy

    def slow_policy(self, x402_version, requirements):
        kept = real_policy(self, x402_version, requirements)
        time.sleep(0.05)
        return kept

    monkeypatch.setattr(SpendGuard, "policy", slow_policy)
    api = FakeAPI(unpaid=unpaid)
    client = make_client(api, wallet_key=DUMMY_KEY, max_spend_usd="0.10")

    results, errors = _concurrent_pulses(client, 8)

    assert client.spent_usd == Decimal("0.06")
    assert len(results) == 1
    assert len(errors) == 7 and all(type(e) is PaymentBlocked for e in errors)
    assert all("CEREBRUS_MAX_SPEND_USD" in e.reason for e in errors)
    assert sum(api.paid_flags) == 1


def test_concurrent_payments_within_budget_all_succeed():
    barrier = threading.Barrier(8, timeout=10)

    def unpaid(req):
        barrier.wait()
        return gateway_402(req.url)

    api = FakeAPI(unpaid=unpaid)
    client = make_client(api, wallet_key=DUMMY_KEY)

    results, errors = _concurrent_pulses(client, 8)

    assert errors == []
    assert len(results) == 8
    assert client.spent_usd == Decimal("0.200")
    assert sum(api.paid_flags) == 8


def test_zero_budget_never_signs():
    api = FakeAPI()
    client = make_client(api, wallet_key=DUMMY_KEY, max_spend_usd=0)
    with pytest.raises(PaymentBlocked):
        client.pulse("BTC")
    assert api.paid_flags == [False]


def test_v1_only_terms_are_never_paid():
    # The API ignores v1 X-PAYMENT, so signing a v1 payment would only waste an
    # authorization. Refuse instead.
    api = FakeAPI(unpaid=lambda req: gateway_402(req.url, v2=False))
    client = make_client(api, wallet_key=DUMMY_KEY)
    with pytest.raises(PaymentBlocked) as exc:
        client.pulse("BTC")
    assert "v2" in exc.value.reason
    assert api.paid_flags == [False]
    assert client.spent_usd == 0


def test_env_allowlist_replaces_the_default(monkeypatch):
    monkeypatch.setenv("CEREBRUS_ALLOWED_PAYTO", f" {OTHER_PAY_TO} , 0x{'22' * 20}")
    api = FakeAPI()
    with pytest.raises(PaymentBlocked):
        make_client(api, wallet_key=DUMMY_KEY).pulse("BTC")

    api = FakeAPI(unpaid=lambda req: gateway_402(req.url, offer(pay_to=OTHER_PAY_TO.lower())))
    client = make_client(api, wallet_key=DUMMY_KEY)
    client.pulse("BTC")
    assert client.spent_usd == Decimal("0.025")


def test_constructor_limits_override_the_environment(monkeypatch):
    monkeypatch.setenv("CEREBRUS_MAX_SPEND_USD", "0")
    api = FakeAPI()
    client = make_client(api, wallet_key=DUMMY_KEY, max_spend_usd="1")
    client.pulse("BTC")
    assert client.spent_usd == Decimal("0.025")


def test_safe_defaults():
    guard = SpendGuard.from_settings()
    assert guard.max_payment_usd == Decimal("0.10")
    assert guard.max_spend_usd == Decimal("1.00")
    assert guard.allowed_pay_to == {PAY_TO.lower()}
    assert guard.allowed_pay_to_solana == frozenset()


@pytest.mark.parametrize("name,value", [
    ("CEREBRUS_MAX_PAYMENT_USD", "ten cents"),
    ("CEREBRUS_MAX_SPEND_USD", "-1"),
    ("CEREBRUS_MAX_SPEND_USD", "NaN"),
    ("CEREBRUS_ALLOWED_PAYTO", "0x1234"),
    ("CEREBRUS_ALLOWED_PAYTO_SOLANA", "0OIl-not-base58"),
])
def test_malformed_limit_fails_closed(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        CerebrusPulse(wallet_key=DUMMY_KEY)


def test_only_usdc_is_paid():
    guard = SpendGuard(Decimal("1"), Decimal("1"), [PAY_TO])
    assert "only USDC" in guard.refusal(offer(asset="0x" + "33" * 20))
    assert "only USDC" in guard.refusal(offer(network="eip155:1"))
    assert guard.refusal(offer()) is None


@pytest.mark.parametrize("amount", ["-5", "0.5", "abc", ""])
def test_unreadable_amount_is_refused(amount):
    guard = SpendGuard(Decimal("1"), Decimal("1"), [PAY_TO])
    bad = offer("0.01").model_copy(update={"amount": amount})
    assert "unreadable amount" in guard.refusal(bad)


# ── Server-side outcomes ────────────────────────────────────────────────────

def test_a_rejected_payment_is_reported_with_terms():
    api = FakeAPI(paid=lambda req: gateway_402(req.url))
    client = make_client(api, wallet_key=DUMMY_KEY)

    with pytest.raises(PaymentRejected) as exc:
        client.pulse("BTC")

    assert exc.value.price_usd == Decimal("0.025")
    assert api.paid_flags == [False, True]
    assert client.spent_usd == Decimal("0.025")  # a signed payment counts


def test_a_failed_paid_retry_is_reported():
    def boom(request):
        raise httpx.ConnectError("connection reset", request=request)

    api = FakeAPI(paid=boom)
    client = make_client(api, wallet_key=DUMMY_KEY)
    with pytest.raises(PaymentFailed) as exc:
        client.pulse("BTC")
    assert "connection reset" in exc.value.detail


# ── Setup ───────────────────────────────────────────────────────────────────

def test_invalid_wallet_key_is_rejected_without_echoing_it():
    with pytest.raises(ValueError) as exc:
        CerebrusPulse(wallet_key="0xdeadbeef")
    assert "deadbeef" not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__


def test_missing_pay_extra_is_explained(monkeypatch):
    monkeypatch.setitem(sys.modules, "x402", None)
    with pytest.raises(ImportError, match=r"cerebrus-pulse\[pay\]"):
        CerebrusPulse(wallet_key=DUMMY_KEY)


def test_own_x402_client_gets_the_spend_limits():
    from eth_account import Account
    from x402 import x402ClientSync
    from x402.mechanisms.evm.exact import register_exact_evm_client

    own = x402ClientSync()
    register_exact_evm_client(own, Account.from_key(DUMMY_KEY))
    api = FakeAPI(unpaid=lambda req: gateway_402(req.url, offer(pay_to=OTHER_PAY_TO)))
    client = make_client(api, x402_client=own)

    with pytest.raises(PaymentBlocked):
        client.pulse("BTC")
    assert api.paid_flags == [False]


def test_x402_client_and_a_key_are_mutually_exclusive():
    from x402 import x402ClientSync

    with pytest.raises(ValueError, match="not both"):
        CerebrusPulse(wallet_key=DUMMY_KEY, x402_client=x402ClientSync())


def test_user_agent_is_sent():
    api = FakeAPI(unpaid=lambda req: httpx.Response(200, json={"status": "ok"}))
    make_client(api).health()
    import cerebrus_pulse

    assert api.requests[0].headers["User-Agent"] == f"cerebrus-pulse-python/{cerebrus_pulse.__version__}"
    assert cerebrus_pulse.__version__ != "0.1.0"


# ── Solana (optional svm extra) ─────────────────────────────────────────────

def test_solana_is_refused_until_its_payto_is_allowlisted():
    solana_offer = offer(network=payment.SOLANA_NETWORK, asset=payment.SOLANA_USDC,
                         pay_to=SOLANA_PAY_TO)
    assert "CEREBRUS_ALLOWED_PAYTO_SOLANA" in SpendGuard.from_settings().refusal(solana_offer)

    guard = SpendGuard.from_settings(allowed_pay_to_solana=[SOLANA_PAY_TO])
    assert guard.refusal(solana_offer) is None
    # base58 is case-sensitive: a case-altered address is a different address
    assert guard.refusal(solana_offer.model_copy(update={"pay_to": SOLANA_PAY_TO.lower()}))


def test_solana_key_registers_the_svm_client():
    pytest.importorskip("solana")
    from solders.keypair import Keypair

    throwaway = str(Keypair())  # random, never funded
    client = CerebrusPulse(solana_key=throwaway, allowed_pay_to_solana=SOLANA_PAY_TO)
    assert client.can_pay


def test_invalid_solana_key_is_rejected_without_echoing_it():
    pytest.importorskip("solana")
    with pytest.raises(ValueError) as exc:
        CerebrusPulse(solana_key="not-a-key")
    assert "not-a-key" not in str(exc.value)
