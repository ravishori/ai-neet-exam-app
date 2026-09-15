"""DATABASE_URL normalization for Railway (single-URL) + local (dual-URL) layouts.

Focused: only exercises the Settings model_validator wired in
``app.core.config``. No env file, no live DB connect, no secrets touched.
"""

from __future__ import annotations

from app.core.config import Settings, _to_async_pg_url, _to_sync_pg_url

JWT = "unit-test-secret-not-a-real-key"


def _s(**overrides) -> Settings:
    """Instantiate Settings without touching apps/backend/.env — every field
    the class considers required must be passed here. Explicitly pins
    ``database_url_sync`` to empty by default so pytest's session-scoped
    conftest env vars (``DATABASE_URL_SYNC``) do not bleed into the derivation
    branch — tests that WANT to override sync pass ``database_url_sync=<val>``.
    """
    base = dict(database_url="postgresql://u:p@h:5432/db", database_url_sync="", jwt_secret=JWT)
    base.update(overrides)
    # _env_file=None tells pydantic-settings to skip the .env file entirely
    # so the test is deterministic regardless of the operator's local env.
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- helpers


def test_helper_normalizes_bare_postgres_scheme():
    assert _to_async_pg_url("postgres://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"
    assert _to_sync_pg_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_helper_normalizes_stdlib_postgresql_scheme():
    assert _to_async_pg_url("postgresql://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"
    assert _to_sync_pg_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_helper_coerces_wrong_driver_tag_for_target_engine():
    # If someone hands us the sync-tagged URL, the async helper still yields asyncpg.
    assert _to_async_pg_url("postgresql+psycopg://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert _to_sync_pg_url("postgresql+asyncpg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"


def test_helper_passes_through_non_postgres_urls():
    assert _to_async_pg_url("sqlite:///./x.db") == "sqlite:///./x.db"
    assert _to_sync_pg_url("") == ""


# --------------------------------------------------------------------------- Railway shape


def test_railway_style_url_is_normalized_to_asyncpg():
    """Railway hands out DATABASE_URL=postgresql://…"""
    settings = _s(database_url="postgresql://ruser:rpass@containers-us-west-42.railway.app:6789/railway")
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.database_url == (
        "postgresql+asyncpg://ruser:rpass@containers-us-west-42.railway.app:6789/railway"
    )


def test_railway_style_url_derives_psycopg_sync_url_when_sync_unset():
    settings = _s(
        database_url="postgresql://ruser:rpass@containers-us-west-42.railway.app:6789/railway",
        database_url_sync="",
    )
    assert settings.database_url_sync == (
        "postgresql+psycopg://ruser:rpass@containers-us-west-42.railway.app:6789/railway"
    )


def test_legacy_postgres_scheme_also_normalizes():
    settings = _s(database_url="postgres://ruser:rpass@h.example.com:5432/mydb")
    assert settings.database_url == "postgresql+asyncpg://ruser:rpass@h.example.com:5432/mydb"
    assert settings.database_url_sync == "postgresql+psycopg://ruser:rpass@h.example.com:5432/mydb"


# --------------------------------------------------------------------------- explicit sync override


def test_explicit_database_url_sync_is_preserved_verbatim():
    """Local .env layouts historically set BOTH URLs. The validator must
    honor an explicit value and NOT rewrite it."""
    explicit = "postgresql+psycopg://local_user:local_pw@localhost:5432/trinetra_db"
    settings = _s(
        database_url="postgresql+asyncpg://local_user:local_pw@localhost:5432/trinetra_db",
        database_url_sync=explicit,
    )
    assert settings.database_url_sync == explicit


def test_explicit_sync_url_wins_even_when_async_url_is_different():
    """Some setups point sync/async at different databases (e.g. a
    read-replica for Alembic). The validator must not overwrite that."""
    settings = _s(
        database_url="postgresql://u:p@primary/db",
        database_url_sync="postgresql+psycopg://u:p@migration-runner/db",
    )
    assert settings.database_url == "postgresql+asyncpg://u:p@primary/db"
    assert settings.database_url_sync == "postgresql+psycopg://u:p@migration-runner/db"


# --------------------------------------------------------------------------- idempotency + safety


def test_already_asyncpg_url_is_unchanged():
    settings = _s(database_url="postgresql+asyncpg://u:p@h:5432/db")
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/db"
    # Sync form still derives correctly.
    assert settings.database_url_sync == "postgresql+psycopg://u:p@h:5432/db"


def test_password_is_not_altered_in_normalization():
    # Ensures the normalizer does not accidentally URL-decode / re-encode
    # credentials. Special chars must round-trip verbatim.
    weird = "p@ss:w/ord+!"
    raw = f"postgresql://u:{weird}@h/db"
    settings = _s(database_url=raw)
    # After scheme swap, the credential body is identical.
    assert settings.database_url == f"postgresql+asyncpg://u:{weird}@h/db"
    assert settings.database_url_sync == f"postgresql+psycopg://u:{weird}@h/db"


def test_sync_field_default_empty_is_populated_by_derivation():
    """DATABASE_URL_SYNC is no longer required as its own env var — the
    validator fills it in when omitted. Nothing else in the settings tree
    should change as a side effect."""
    settings = _s(database_url="postgresql://u:p@h/db")
    # The derived value is present and driver-tagged psycopg.
    assert settings.database_url_sync.startswith("postgresql+psycopg://")


def test_normalizer_helpers_never_print(capsys):
    """The two normalization helpers must never write the URL to stdout /
    stderr — a defensive check against future edits that add debug logging."""
    _to_async_pg_url("postgresql://user:SECRET@h:5432/db")
    _to_sync_pg_url("postgresql://user:SECRET@h:5432/db")
    captured = capsys.readouterr()
    assert "SECRET" not in captured.out
    assert "SECRET" not in captured.err
