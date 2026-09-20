"""Production Seed V2 practice allowlist — server-owned membership.

Resolves exclusively from the frozen V2 publication authorization artifact.
Clients may request scope_type=SEED_V2 only; they cannot inject UUIDs.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from functools import lru_cache
from pathlib import Path

EXPECTED_ALLOWLIST_SHA256 = "a3a8242433b69e80b1754807949767318fa19c41699ecea42c4c246b035b3978"
AUTHORIZATION_RELPATH = Path("docs/audits/TALOS_PRODUCTION_SEED_V2_PUBLICATION_AUTHORIZATION_20260904.json")
SCOPE_TYPE = "SEED_V2"
ALLOWLIST_COUNT = 100
SEED_V2_SUPERSEDED_TAGS: tuple[str, ...] = (
    "seed-v2-rematerialization-superseded-20260903",
    "seed-v2-numerical-remediation-superseded-20260904",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def allowlist_sha(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def load_seed_v2_allowlist() -> tuple[tuple[str, ...], str]:
    """Return (ordered UUID strings, sha256) from the authoritative artifact."""
    path = _repo_root() / AUTHORIZATION_RELPATH
    if not path.is_file():
        raise FileNotFoundError(f"Seed V2 authorization artifact missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = list(data.get("exact_allowlist") or data.get("exact_uuid_allowlist") or [])
    computed = allowlist_sha(ids)
    embedded = data.get("allowlist_sha256")
    if len(ids) != ALLOWLIST_COUNT:
        raise ValueError(f"Seed V2 allowlist must contain exactly {ALLOWLIST_COUNT} UUIDs, got {len(ids)}")
    if computed != EXPECTED_ALLOWLIST_SHA256:
        raise ValueError(f"Seed V2 allowlist hash mismatch: {computed}")
    if embedded and embedded != EXPECTED_ALLOWLIST_SHA256:
        raise ValueError(f"Seed V2 embedded allowlist_sha256 mismatch: {embedded}")
    for raw in ids:
        uuid.UUID(raw)
    return tuple(ids), computed


def seed_v2_uuid_strings() -> list[str]:
    ids, _ = load_seed_v2_allowlist()
    return list(ids)


def seed_v2_uuids() -> list[uuid.UUID]:
    return [uuid.UUID(x) for x in seed_v2_uuid_strings()]


def seed_v2_allowlist_sha256() -> str:
    _, sha = load_seed_v2_allowlist()
    return sha


def clear_seed_v2_allowlist_cache() -> None:
    """Test helper — clears lru_cache after monkeypatching paths."""
    load_seed_v2_allowlist.cache_clear()
