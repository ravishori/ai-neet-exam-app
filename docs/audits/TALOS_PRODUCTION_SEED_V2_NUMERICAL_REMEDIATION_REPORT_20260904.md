# Production Seed V2 — Numerical Remediation Report

**Verdict: AMBER**

Captured: `2026-09-03T18:46:28.173381+00:00` (finalize; artifacts updated after tests)

Controlled remediation of the four NCERT-certification numerical failures only. Active population remains exactly 100. All replacements are DRAFT. No approval, publication, ECAEP, or NCERT re-run.

## Verdict rationale

| Gate | Result |
|------|--------|
| Independent numerical verification (all 4) | PASS |
| Correct result in options exactly once (family rules) | PASS |
| Lineage / originals preserved | PASS |
| Active count = 100; protected populations unchanged | PASS |
| DRAFT only; approvals/publications/ECAEP = 0 | PASS |
| Semantic ambiguity hard-fail | none |
| Soft semantic review (`SEMANTIC_REVIEW_REQUIRED`) | physics-10, physics-11 |

AMBER (not GREEN): soft semantic review signals on 2/4 replacements. AMBER (not RED): no numerical FAIL, no lineage loss, no integrity mutation.

## Exact four slots

| Slot | Original ID | Replacement ID | Orig stored → independent | Repl stored / independent |
|------|-------------|----------------|---------------------------|---------------------------|
| physics-10 | `4304a3ef-…59f8` | `2e43ef71-…de8b1` | A → C (J=8, ΔKE=24) | B / B PASS |
| physics-11 | `223c5cdf-…2d33` | `5b4f381e-…d0f5` | C → B (Kf=24) | B / B PASS |
| physics-20 | `03f040b6-…dabd` | `f60e3124-…dce9` | A → B (ΔL=2.0e-3) | A / A PASS |
| physics-34 | `690202d2-…833a` | `b98e5873-…ce6f7` | A → +7.5 cm absent | B / B PASS |

### physics-10 — inelastic collision / impulse + KE loss

- Equations: `v=(m1·v1)/(m1+m2)`, `J_on_2=m2·v`, `ΔKE=½m1v1²−½(m1+m2)v²`
- Inputs: m1=3 kg, v1=8 m/s, m2=5 kg
- Computed: impulse on stationary = 15 N·s, KE loss = 60 J, v_common = 3 m/s
- Stored answer B matches independent result; explanation consistent
- Soft semantic: HIGH_OPTION_OVERLAP on compound impulse/KE distractors (shared lexical skeleton; distinct KE values)

### physics-11 — work–energy with F(x)

- Equations: `W=∫(a x² + b x) dx`, `Kf=Ki+W`
- Inputs: a=6, b=−4, x∈[1,3], Ki=10 J → W=36 J, Kf=46 J
- Stored answer B matches; options uniquely contain 46 J
- Soft semantic: EXPLANATION_REFERENCES_MULTIPLE_OPTIONS + false-positive HIGH_OPTION_OVERLAP on short numeric options

### physics-20 — Young’s modulus elongation

- Equation: `ΔL = F L / (A Y)`
- Inputs: F=1.5×10³ N, L=1.8 m, A=3.0×10⁻⁵ m², Y=7.0×10¹⁰ N/m²
- Computed: ΔL ≈ 1.29×10⁻³ m → option A only
- Semantic: STRUCTURALLY_VALID

### physics-34 — thin lens image shift

- Equations: `1/v − 1/u = 1/f`, `shift = v2 − v1`
- Inputs: f=+10 cm, u1=−30 cm, u2=−15 cm
- Computed: v1=+15 cm, v2=+30 cm, shift = +15 cm **away** → option B only
- Magnitude-only option scan sees A/B both “15 cm”; direction-aware matcher uniquely selects B (original failure class was absent correct value)

## Provider lineage

- Provider: Gemini · Model: `gemini-3.6-flash` · Routing: `fixed:gemini` · Fallback: 0
- Cumulative attempts: 11 · Created candidates: 7 · Cost USD: **0.031951**
- Finalize accepted four independently verified prior attempts (no additional LLM calls in finalize)
- Rejected attempts retained as DRAFT with `seed-v2-numerical-remediation-attempt-failed-20260904`

## Lineage tags

- Active remat: `seed-v2-numerical-remediation-20260904`
- Superseded originals: `seed-v2-numerical-remediation-superseded-20260904`
- Originals remain DRAFT with recoverable stem/options/answer/explanation

## Integrity

- Active V2 slots: **100** (before and after)
- Non-target 96 unchanged
- V1 / T6-D / T6-F2 / legacy / prior visual-superseded fingerprints unchanged
- Approvals = 0 · Publications = 0 · ECAEP = 0 · NCERT re-run = false

## Tests

- `tests/test_seed_v2_numerical_remediation.py` — **8 passed** (includes original failure-class regressions + thin-lens u1/u2 forms)
- `tests/test_factory_seed_diversity.py` + `tests/test_seed_v2_p5_remediation.py` — **27 passed**
- Thresholds not weakened

## Remaining limitations

1. Full NCERT certification on the remediated active 100 is **not** done.
2. Soft semantic review flags on physics-10/11 (no hard ambiguity).
3. NCERT source paths preserved per slot plan; replacements still need the separate NCERT re-run for evidence refresh.

## Next gate

**NCERT Certification Re-run — Exact Active 100**

## STOP

No NCERT re-run in this task · no approve · no publish · no ECAEP · no regenerate of the other 96 · no 1,000-question scale · no deploy.
