"""Release guard for the SDK's default payee.

``DEFAULT_ALLOWED_PAYTO`` in ``src/cerebrus_pulse/payment.py`` is the Base payTo
every install pays with no configuration. A release (sdist or wheel) is not
built while that default is an address being replaced. Order of work: move the
API to the new payTo, check its 402 names it, then set DEFAULT_ALLOWED_PAYTO and
the README table to it. Editable installs, used for development, are not checked.
"""

from __future__ import annotations

import re
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Base payTo addresses that must not ship as the default again (lowercase).
REPLACED_PAYTO = frozenset({"0xfdfb12764c76b5113153acaa2317081f4abc2a88"})

_DEFAULT_RE = re.compile(r'^DEFAULT_ALLOWED_PAYTO = "([^"]*)"$', re.MULTILINE)


def release_blocker(root: str | Path) -> str | None:
    """Why a release must not be built from ``root``, or None."""
    source = Path(root, "src", "cerebrus_pulse", "payment.py").read_text(encoding="utf-8")
    match = _DEFAULT_RE.search(source)
    if match is None:
        return "cannot find DEFAULT_ALLOWED_PAYTO in src/cerebrus_pulse/payment.py"
    if match.group(1).lower() in REPLACED_PAYTO:
        return (
            f"DEFAULT_ALLOWED_PAYTO is {match.group(1)}, a payTo being replaced. "
            "Move the API to the new payTo first, then set DEFAULT_ALLOWED_PAYTO "
            "and the README table to it (see hatch_build.py)."
        )
    return None


class ReleaseGuard(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        if version == "editable":
            return
        reason = release_blocker(self.root)
        if reason:
            raise RuntimeError(f"refusing to build a release: {reason}")
