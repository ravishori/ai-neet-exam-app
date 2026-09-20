# P2.2-R1 Validation Report

Generated: 2026-09-01T18:39:00.110023+00:00

## Input
- Generated candidates: 1000
- Structurally valid Gemini: 326

## Independent Validator
- Provider: openai
- Processed: 326
- PASS: 254 | FAIL: 72 | INCONCLUSIVE: 0

## Quality
{
  "true_acceptance_rate": 0.7791,
  "production_ready_rate": 0.7699,
  "minor_revision_rate": 0.0092,
  "false_pass_rate": 0.0,
  "ambiguity_rate": 0.6902,
  "duplicate_rate": 0.0,
  "answer_accuracy_proxy": 0.773,
  "grades": {
    "A": 251,
    "D": 72,
    "B": 3
  }
}

## Economics
{
  "generation_cost_usd": 0.634725,
  "validation_cost_usd": 0.0,
  "total_cost_usd": 0.634725,
  "cost_per_generated_question_usd": 0.000635,
  "cost_per_structurally_valid_usd": 0.001947,
  "cost_per_independently_validated_usd": 0.002499,
  "cost_per_human_accepted_usd": null,
  "cost_per_human_accepted_inr": null,
  "inr_note": "INR conversion omitted \u2014 no recorded exchange-rate basis in P2.2 artifacts"
}

**Final verdict:** GREEN
**Next action:** SCALE

Production import: BLOCKED
