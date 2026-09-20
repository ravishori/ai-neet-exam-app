# P2.2 Live AI Pilot Specification

**Phase:** P2.2 Live  
**Prerequisite:** P2.2 dry-run pilot COMPLETE  
**Production import:** BLOCKED  

## Objective

Controlled live API experiment across two tracks:

1. **Track A** — 40 stratified PYQ source-recovery candidates (30–50 range)
2. **Track B** — 1,000 NCERT-grounded NEET MCQs (not PYQs)

## Safety

- R3 immutable (`p2_1e_full_r3/`)
- Output: `data/staging/pyq/2020-2025/p2_2_live_pilot/`
- Zero production PostgreSQL writes
- `--confirm` required before any API spend
- Budget cap: `P2_2_LIVE_MAX_COST_USD` (default 75)

## Track A

- Sources: existing `PYQ_P2_2_TRIAGE.json` population
- Providers: Gemini, OpenAI, Anthropic via `GatewayRecoveryProvider`
- Independent OCR validation (not same-model self-judge)
- Human gold standard: `PYQ_P2_2_HUMAN_REVIEW.csv` (PENDING until reviewer fills)

## Track B

- Sources: `StudyMaterial/` NCERT PDFs only (page-level text extraction)
- 1,000 MCQs with reproducible provider cohort (index mod 3)
- Generation + independent model review per MCQ
- Duplicate detection (exact + near)
- Human sample: 100 stratified MCQs in review CSV

## Run

```bash
cd apps/backend
.venv/Scripts/python.exe scripts/run_pyq_p2_2_live_pilot.py --confirm
```

Optional flags: `--recovery-count`, `--mcq-count`, `--max-cost-usd`, `--seed`, `--mcq-concurrency`

## Verdicts

| Verdict | Meaning |
|---------|---------|
| GREEN | Scale candidate — fidelity, cost, review burden acceptable |
| YELLOW | Refine pipeline/providers before scale |
| RED | Abandon or redesign |

## Artifacts

- `docs/content-factory/PYQ_P2_2_LIVE_PILOT_REPORT.json`
- `docs/content-factory/PYQ_P2_2_LIVE_PILOT_REPORT.md`
- `docs/content-factory/PYQ_P2_2_PROVIDER_COMPARISON.json`
- `docs/content-factory/PYQ_P2_2_RECOVERY_RESULTS.jsonl`
- `docs/content-factory/PYQ_P2_2_MCQ_RESULTS.jsonl`
- `docs/content-factory/PYQ_P2_2_HUMAN_REVIEW.csv`

## Success criteria

Not volume — **source fidelity**, **NCERT support**, **false recovery**, **human acceptance**, **cost per usable question**, **review burden**.
