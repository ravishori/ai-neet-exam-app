"""Production Seed V1 practice allowlist — server-owned membership.

Resolves exclusively from the frozen publication authorization artifact.
Clients may request scope_type=SEED_V1 only; they cannot inject UUIDs.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from functools import lru_cache
from pathlib import Path

EXPECTED_ALLOWLIST_SHA256 = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"
AUTHORIZATION_RELPATH = Path("docs/audits/TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json")
SCOPE_TYPE = "SEED_V1"


def _repo_root() -> Path:
    # apps/backend/app/modules/assessment/seed_v1_allowlist.py → repo root is parents[5]
    return Path(__file__).resolve().parents[5]


def allowlist_sha(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def load_seed_v1_allowlist() -> tuple[tuple[str, ...], str]:
    """Return (ordered UUID strings, sha256) from the authoritative artifact."""
    path = _repo_root() / AUTHORIZATION_RELPATH
    if not path.is_file():
        raise FileNotFoundError(f"Seed V1 authorization artifact missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = list(data.get("exact_uuid_allowlist") or [])
    computed = allowlist_sha(ids)
    embedded = data.get("allowlist_sha256")
    if len(ids) != 30:
        raise ValueError(f"Seed V1 allowlist must contain exactly 30 UUIDs, got {len(ids)}")
    if computed != EXPECTED_ALLOWLIST_SHA256:
        raise ValueError(f"Seed V1 allowlist hash mismatch: {computed}")
    if embedded and embedded != EXPECTED_ALLOWLIST_SHA256:
        raise ValueError(f"Seed V1 embedded allowlist_sha256 mismatch: {embedded}")
    # Validate UUID shape; reject injection of non-UUID strings at load time.
    for raw in ids:
        uuid.UUID(raw)
    return tuple(ids), computed


def seed_v1_uuid_strings() -> list[str]:
    ids, _ = load_seed_v1_allowlist()
    return list(ids)


def seed_v1_uuids() -> list[uuid.UUID]:
    return [uuid.UUID(x) for x in seed_v1_uuid_strings()]


def seed_v1_allowlist_sha256() -> str:
    _, sha = load_seed_v1_allowlist()
    return sha


def clear_seed_v1_allowlist_cache() -> None:
    """Test helper — clears lru_cache after monkeypatching paths."""
    load_seed_v1_allowlist.cache_clear()
