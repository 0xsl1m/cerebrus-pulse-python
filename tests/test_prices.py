"""Advertised prices must match what the API published (F026, F074).

The SDK does not decide prices: the 402 terms do, and the spend limits cap
them. But the docstrings, README and INDICATIVE_PRICES_USD (which the
LangChain tools show to the model) must not drift from the API.

fixtures/well_known_x402.json is https://api.cerebruspulse.xyz/.well-known/x402
as fetched on 2026-09-24 (the same copy the MCP server's tests use).
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import cerebrus_pulse
from cerebrus_pulse import INDICATIVE_PRICES_USD, CerebrusPulse

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((Path(__file__).parent / "fixtures" / "well_known_x402.json")
                      .read_text(encoding="utf-8"))

# SDK method -> the manifest's path for it
METHOD_PATHS = {
    "pulse": "/pulse/*",
    "sentiment": "/sentiment",
    "funding": "/funding/*",
    "bundle": "/bundle/*",
    "screener": "/screener",
    "oi": "/oi/*",
    "spread": "/spread/*",
    "correlation": "/correlation",
    "stress": "/arb",
    "cex_dex": "/cex-dex/*",
    "basis": "/basis/*",
    "depeg": "/depeg",
    "liquidations": "/liquidations/*",
}


def manifest_prices() -> dict[str, Decimal]:
    return {
        re.sub(r"^https?://[^/]+", "", e["url"]): Decimal(str(e["price"]["amount"]))
        for e in MANIFEST["endpoints"]
    }


def test_indicative_prices_match_the_manifest():
    published = manifest_prices()
    assert set(METHOD_PATHS.values()) == set(published), "an endpoint has no SDK method"
    assert set(INDICATIVE_PRICES_USD) == set(METHOD_PATHS)
    for method, path in METHOD_PATHS.items():
        assert INDICATIVE_PRICES_USD[method] == published[path], method


def test_docstrings_quote_the_indicative_price():
    for method, price in INDICATIVE_PRICES_USD.items():
        doc = getattr(CerebrusPulse, method).__doc__
        quoted = re.findall(r"Indicative cost: \$([0-9.]+) USDC", doc)
        assert quoted == [str(price)], method
        assert "discount" not in doc, method


def test_readme_price_table_matches():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| `(\w+)\(\)` \| `[^`]+` \| \$([0-9.]+) \|$", readme, re.M))
    assert {k: Decimal(v) for k, v in rows.items()} == INDICATIVE_PRICES_USD
    assert "discount" not in readme


def test_version_comes_from_the_package_metadata():
    from importlib.metadata import version

    assert cerebrus_pulse.__version__ == version("cerebrus-pulse")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{cerebrus_pulse.__version__}"' in pyproject
