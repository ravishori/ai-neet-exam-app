"""V2 publication authorization allowlist / firewall unit tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NCERT = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_NCERT_CERTIFICATION_RERUN_20260904.json"
NUM = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_NUMERICAL_REMEDIATION_20260904.json"
V1 = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"


def _sha(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest()


def test_exact_100_allowlist_from_ncert_rerun():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    assert ncert["verdict"] == "GREEN"
    ids = ncert["active_population"]["item_ids"]
    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert ncert["active_population"]["subject_counts"] == {
        "Physics": 35,
        "Chemistry": 35,
        "Botany": 15,
        "Zoology": 15,
    }
    assert ncert["decision_counts"].get("FAIL", 0) == 0
    assert ncert["decision_counts"].get("REQUIRES_HUMAN_REVIEW", 0) == 0


def test_wrong_id_rejected_against_allowlist():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    allow = set(ncert["active_population"]["item_ids"])
    bogus = "00000000-0000-0000-0000-000000000000"
    assert bogus not in allow


def test_superseded_and_historical_excluded():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    allow = set(ncert["active_population"]["item_ids"])
    hist = set(ncert["active_population"]["historical_excluded"])
    assert len(hist) == 8
    assert allow.isdisjoint(hist)


def test_protected_v1_not_in_v2_allowlist():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    v1 = json.loads(V1.read_text(encoding="utf-8"))
    allow = set(ncert["active_population"]["item_ids"])
    v1_ids = set(v1["exact_uuid_allowlist"])
    assert allow.isdisjoint(v1_ids)
    assert len(v1_ids) == 30


def test_numerical_replacements_are_current_active_ids():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    num = json.loads(NUM.read_text(encoding="utf-8"))
    allow = set(ncert["active_population"]["item_ids"])
    repl = num["active_population"]["numerical_replacements"]
    for sid in ("physics-10", "physics-11", "physics-20", "physics-34"):
        assert repl[sid] in allow
    # originals must not be active
    for r in num["results"]:
        assert r["original_content_item_id"] not in allow


def test_certification_requirement_all_certified_with_limitation_or_certified():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    for it in ncert["items"]:
        assert it["certification_decision"] in ("CERTIFIED", "CERTIFIED_WITH_LIMITATION")
        assert it["item_id"] in ncert["active_population"]["item_ids"]


def test_allowlist_sha_stable_ordering_dependent():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    ids = list(ncert["active_population"]["item_ids"])
    sha1 = _sha(ids)
    sha2 = _sha(list(reversed(ids)))
    assert sha1 != sha2  # order matters — publication must use frozen order
    assert len(sha1) == 64


def test_visual_slots_present():
    ncert = json.loads(NCERT.read_text(encoding="utf-8"))
    by_slot = ncert["active_population"].get("ids_by_slot") or {
        it["slot_id"]: it["item_id"] for it in ncert["items"]
    }
    for sid in ("physics-05", "physics-21", "zoology-12"):
        assert sid in by_slot
        assert by_slot[sid] in ncert["active_population"]["item_ids"]
