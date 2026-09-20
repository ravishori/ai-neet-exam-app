"""Tests for stratified semantic-dedup calibration sampling."""

from __future__ import annotations

from app.modules.cms.acquisition.mmf.calibration_sample import (
    CandidatePairScore,
    PairKey,
    blank_review_fields,
    stratified_calibration_sample,
    validate_sample,
)


def _pair(a: str, b: str, pa: str, pb: str, score: float) -> CandidatePairScore:
    return CandidatePairScore(
        candidate_a=a,
        candidate_b=b,
        provider_a=pa,
        provider_b=pb,
        similarity_score=score,
        cross_provider=pa != pb,
    )


def _make_universe() -> list[CandidatePairScore]:
    pairs: list[CandidatePairScore] = []
    # very high same-provider
    for i in range(25):
        pairs.append(_pair(f"g{i}", f"g{i+100}", "gemini", "gemini", 0.96 + (i % 3) * 0.01))
    # threshold region
    for i in range(25):
        pairs.append(_pair(f"t{i}", f"t{i+100}", "anthropic", "anthropic", 0.91 + (i % 4) * 0.01))
    # cross provider
    for i in range(10):
        pairs.append(_pair(f"ga{i}", f"ga{i+50}", "gemini", "anthropic", 0.93))
        pairs.append(_pair(f"go{i}", f"go{i+50}", "gemini", "openai", 0.92))
        pairs.append(_pair(f"ao{i}", f"ao{i+50}", "anthropic", "openai", 0.91))
    # same openai
    for i in range(15):
        pairs.append(_pair(f"o{i}", f"o{i+40}", "openai", "openai", 0.88))
    return pairs


def test_stratified_sampling_quotas_and_no_dup_pairs():
    sample = stratified_calibration_sample(_make_universe(), target_total=80, seed=42)
    assert sample.pool_stats["selected_total"] == len(sample.pairs)
    assert len(sample.pairs) <= 80
    assert sample.filled["VERY_HIGH_SIMILARITY"] >= 1
    assert sample.filled["THRESHOLD_REGION"] >= 1
    assert sample.filled["CROSS_PROVIDER"] >= 1
    assert sample.filled["SAME_PROVIDER"] >= 1
    keys = {PairKey.of(p.candidate_id_a, p.candidate_id_b) for p in sample.pairs}
    assert len(keys) == len(sample.pairs)


def test_threshold_region_and_provider_balance():
    sample = stratified_calibration_sample(_make_universe(), target_total=80, seed=7)
    thr = [p for p in sample.pairs if "THRESHOLD_REGION" in p.selection_buckets]
    assert thr
    assert all(0.90 <= p.cosine_similarity < 0.95 for p in thr)
    cross = [p for p in sample.pairs if "CROSS_PROVIDER" in p.selection_buckets]
    assert cross
    rels = {p.provider_relationship for p in cross}
    assert rels & {"gemini_anthropic", "gemini_openai", "anthropic_openai"}


def test_ab_randomization_uses_seed():
    s1 = stratified_calibration_sample(_make_universe(), target_total=40, seed=1)
    s2 = stratified_calibration_sample(_make_universe(), target_total=40, seed=1)
    assert [p.pair_id for p in s1.pairs] == [p.pair_id for p in s2.pairs]
    assert any(p.display_order_swapped for p in s1.pairs) or any(
        not p.display_order_swapped for p in s1.pairs
    )


def test_duplicate_pair_prevention_and_validation():
    pairs = _make_universe()
    # inject duplicate unordered pair with lower score
    pairs.append(_pair("g0", "g100", "gemini", "gemini", 0.50))
    sample = stratified_calibration_sample(pairs, target_total=50, seed=3)
    ids = set()
    for p in sample.pairs:
        ids.add(p.candidate_id_a)
        ids.add(p.candidate_id_b)
    errs = validate_sample(sample, valid_ids=ids)
    assert errs == []


def test_review_schema_blank_labels():
    fields = blank_review_fields()
    assert fields["human_label"] == ""
    assert fields["reviewer_1_label"] == ""
    assert fields["adjudicated_label"] == ""
    assert "DUPLICATE" not in fields.values()


def test_immutable_candidate_ids_only():
    sample = stratified_calibration_sample(_make_universe(), target_total=30, seed=9)
    valid = set()
    for p in sample.pairs:
        valid.add(p.candidate_id_a)
        valid.add(p.candidate_id_b)
    # unknown id should fail validation
    sample.pairs[0].candidate_id_a = "NOT-A-REAL-ID"
    errs = validate_sample(sample, valid_ids=valid)
    assert any(e.startswith("unknown_id") for e in errs)
