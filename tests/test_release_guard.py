"""The release guard (hatch_build.py) and the documented default payee.

The hook is loaded with a stand-in for hatchling's base class, so these tests
need no build backend and build nothing.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from cerebrus_pulse import payment

ROOT = Path(__file__).resolve().parent.parent
NEW_PAY_TO = "0x000000000000000000000000000000000000bEEF"


@pytest.fixture
def hook(monkeypatch):
    interface = types.ModuleType("hatchling.builders.hooks.plugin.interface")
    interface.BuildHookInterface = object
    for name in ("hatchling", "hatchling.builders", "hatchling.builders.hooks",
                 "hatchling.builders.hooks.plugin"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, interface.__name__, interface)
    spec = importlib.util.spec_from_file_location("hatch_build", ROOT / "hatch_build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project(tmp_path, pay_to):
    source = tmp_path / "src" / "cerebrus_pulse" / "payment.py"
    source.parent.mkdir(parents=True)
    source.write_text(f'X = 1\nDEFAULT_ALLOWED_PAYTO = "{pay_to}"\n', encoding="utf-8")
    return tmp_path


def guard(hook, root):
    instance = hook.ReleaseGuard()
    instance.root = str(root)
    return instance


def test_a_release_is_refused_while_the_default_is_a_replaced_payto(hook, tmp_path):
    replaced = next(iter(hook.REPLACED_PAYTO))
    root = project(tmp_path, replaced.upper().replace("0X", "0x"))

    assert "DEFAULT_ALLOWED_PAYTO" in hook.release_blocker(root)
    for version in ("standard", "unknown-future-version"):
        with pytest.raises(RuntimeError, match="refusing to build a release"):
            guard(hook, root).initialize(version, {})
    guard(hook, root).initialize("editable", {})  # development installs still work


def test_a_release_is_built_once_the_default_is_a_new_payto(hook, tmp_path):
    root = project(tmp_path, NEW_PAY_TO)
    assert hook.release_blocker(root) is None
    guard(hook, root).initialize("standard", {})


def test_a_default_the_guard_cannot_read_blocks_the_release(hook, tmp_path):
    root = project(tmp_path, NEW_PAY_TO)
    source = root / "src" / "cerebrus_pulse" / "payment.py"
    source.write_text("DEFAULT_ALLOWED_PAYTO = get_default()\n", encoding="utf-8")
    assert "cannot find" in hook.release_blocker(root)


def test_the_guard_reads_this_repo_default(hook):
    blocked = hook.release_blocker(ROOT) is not None
    assert blocked == (payment.DEFAULT_ALLOWED_PAYTO.lower() in hook.REPLACED_PAYTO)


def test_readme_documents_the_default_payto():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"| `{payment.DEFAULT_ALLOWED_PAYTO}` |" in readme
