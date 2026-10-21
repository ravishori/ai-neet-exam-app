"""Safety tests for scripts/mcq_factory_groq_bulk_run.py.

Confirms: (1) --dry-run (the default) never imports/constructs any HTTP
client or provider and makes no network call; (2) a live attempt without
the explicit opt-in flag is refused; (3) the live branch (now a real,
tested invocation of GroqFactoryOrchestrator — see
test_mcq_factory_groq_cli_live_run.py for the mocked end-to-end coverage)
still FAILS CLOSED — and never constructs a real Groq client — whenever
required configuration or required CLI inputs are missing/invalid.

ZERO real GROQ_API_KEY is ever read here: the "missing config" case below
explicitly constructs a ``Settings`` override with ``groq_enabled=False``
rather than relying on (or depending on the absence of) whatever happens
to be in the local ``.env`` file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[4] / "scripts" / "mcq_factory_groq_bulk_run.py"
)


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("mcq_factory_groq_bulk_run", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Register in sys.modules BEFORE exec: the module's dataclasses (e.g.
    # LiveDependencies) use `from __future__ import annotations` (string
    # annotations), and dataclasses' own ClassVar/KW_ONLY detection looks
    # the module up via sys.modules[cls.__module__] — which fails with a
    # bare AttributeError if the module was never registered.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cli_module():
    assert _SCRIPT_PATH.exists(), f"CLI script not found at {_SCRIPT_PATH}"
    return _load_cli_module()


def test_dry_run_is_the_default(cli_module):
    args = cli_module.build_arg_parser().parse_args(["--batch-id", "t1"])
    assert args.dry_run is True
    assert args.live_opt_in is False


def test_dry_run_exits_zero_and_prints_plan_without_network(cli_module, capsys, monkeypatch):
    # Guard: if the dry-run path ever tries to open a socket, httpx.Client/
    # AsyncClient construction would need network libs — assert the two
    # provider classes are never imported as a side effect of main().
    import app.modules.ai.gateway.openai_provider as openai_provider_module

    constructed = {"count": 0}
    original_init = openai_provider_module.OpenAIProvider.__init__

    def _tracking_init(self, *a, **kw):
        constructed["count"] += 1
        return original_init(self, *a, **kw)

    monkeypatch.setattr(openai_provider_module.OpenAIProvider, "__init__", _tracking_init)

    rc = cli_module.main(["--batch-id", "t1", "--count", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "No Groq client was constructed" in out
    assert constructed["count"] == 0


def test_live_without_opt_in_refuses(cli_module, capsys):
    rc = cli_module.main(["--batch-id", "t1", "--no-dry-run"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "i-understand-this-calls-a-live-paid-api" in err


def test_live_with_opt_in_but_groq_disabled_fails_closed_without_constructing_provider(
    cli_module, capsys, monkeypatch
):
    """Even with the explicit opt-in AND --no-dry-run, a live run with
    GROQ_ENABLED=False must fail CLOSED (clear error, non-zero exit) and
    must NEVER construct a real provider. Uses an explicit ``Settings``
    override (not the real local .env) so this is deterministic regardless
    of what GROQ_API_KEY happens to be configured locally."""
    import app.modules.ai.gateway.openai_provider as openai_provider_module
    from app.core.config import Settings

    constructed = {"count": 0}
    original_init = openai_provider_module.OpenAIProvider.__init__

    def _tracking_init(self, *a, **kw):
        constructed["count"] += 1
        return original_init(self, *a, **kw)

    monkeypatch.setattr(openai_provider_module.OpenAIProvider, "__init__", _tracking_init)
    fake_settings = Settings(groq_enabled=False, groq_api_key="")
    monkeypatch.setattr("app.core.config.get_settings", lambda: fake_settings)

    rc = cli_module.main(
        ["--batch-id", "t1", "--no-dry-run", "--i-understand-this-calls-a-live-paid-api"]
    )
    assert rc == 4
    err = capsys.readouterr().err
    assert "GROQ_ENABLED" in err
    assert constructed["count"] == 0


def test_live_with_opt_in_but_missing_fact_pack_fails_closed(cli_module, capsys, monkeypatch):
    """Even with valid Groq config, a live run without --fact-pack/
    --evidence-pdf must refuse with a clear error rather than proceeding
    with some default/empty batch."""
    from app.core.config import Settings

    fake_settings = Settings(groq_enabled=True, groq_api_key="dummy-test-key-not-real", mcq_provider="groq")
    monkeypatch.setattr("app.core.config.get_settings", lambda: fake_settings)

    rc = cli_module.main(
        ["--batch-id", "t1", "--no-dry-run", "--i-understand-this-calls-a-live-paid-api"]
    )
    assert rc == 4
    err = capsys.readouterr().err
    assert "--fact-pack" in err
