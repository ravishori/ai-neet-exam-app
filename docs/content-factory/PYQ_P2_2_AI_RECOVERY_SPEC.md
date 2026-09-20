# P2.2 — AI-Assisted Source Recovery Specification

**Phase:** P2.2  
**Status:** Pilot (dry-run)  
**Production import:** BLOCKED  

## Purpose

Controlled AI-assisted **source reconstruction** for R3 PARTIAL and C-grade fidelity cases in the NEET PYQ corpus (2020–2025). This is not question generation — recovered text must be supported by original source evidence.

## Core principle

```text
AI_RECOVERED != VERIFIED
```

A record becomes `VERIFIED` only after independent validation against source evidence. R3 `VALID`/`PARTIAL` statuses are never overwritten.

## Source hierarchy

1. Original PYQ PDF / source evidence  
2. OCR text  
3. OCR word coordinates / geometry  
4. Existing R3 extraction  
5. R1/R2 extraction (comparison only)  
6. AI interpretation (never authoritative)

## Immutable inputs

Never modify:

- `data/staging/pyq/2020-2025/p2_1e_full/`
- `data/staging/pyq/2020-2025/p2_1e_full_r2/`
- `data/staging/pyq/2020-2025/p2_1e_full_r3/`
- P2.1E / P2.1F / P2.1G audit artifacts

## Output store

All recovery artifacts:

```text
data/staging/pyq/2020-2025/p2_2_ai_recovery/
```

## Pipeline phases

| Phase | Module | Description |
|-------|--------|-------------|
| 1 | `triage.py` | Classify PARTIAL + C-grade into deterministic / AI / human / insufficient |
| 2 | `evidence.py` | Check PDF, OCR words, raw block availability |
| 3 | `evidence.py` | Build structured evidence package + hash |
| 4 | `deterministic.py` | Reparse raw block before any AI call |
| 5 | `providers.py` | Provider-neutral recovery (`DryRun`, `Gateway`) |
| 6 | `validation.py` | Independent source validation (PASS/FAIL/INCONCLUSIVE) |
| 7 | `consensus.py` | Multi-provider field comparison |
| 8 | `pipeline.py` | Orchestration, pilot selection, artifact emission |
| 9 | `cache.py` | Immutable cache keyed by evidence + request hash |

## Triage categories

- `DETERMINISTIC_RECOVERABLE` — raw block reparse may fix missing fields  
- `AI_MULTIMODAL_RECOVERABLE` — OCR fragmentation, math, chemistry, layout  
- `HUMAN_REVIEW` — diagrams, severe fragmentation, ambiguity  
- `SOURCE_INSUFFICIENT` — no PDF/OCR/raw evidence  

## AI output contract

```json
{
  "status": "RECOVERED|NOT_RECOVERABLE|INCONCLUSIVE",
  "stem": "...",
  "options": {"1": "...", "2": "...", "3": "...", "4": "..."},
  "changed_fields": [],
  "source_evidence_used": [],
  "uncertainties": [],
  "foreign_text_detected": false,
  "confidence": 0.0
}
```

## Recovery metadata (per record)

```json
{
  "original_status": "PARTIAL",
  "recovery_status": "AI_RECOVERED|DETERMINISTIC_RECOVERED|NOT_RECOVERABLE|INCONCLUSIVE",
  "verification_status": "PENDING|VERIFIED|FAILED|HUMAN_REVIEW|NOT_APPLICABLE|INCONCLUSIVE"
}
```

## Provider routing

Staged escalation (pilot uses dry-run):

```text
Candidate → deterministic first → primary provider → low confidence → secondary provider → validation
```

Model agreement does not imply correctness. `UNANIMOUS ≠ VERIFIED`.

## Pilot gate

- Population: 50–100 stratified records  
- Default mode: **dry-run** (no API calls, no DB writes)  
- Metrics: recovery rate, source fidelity, false recovery, provider agreement, human-review rate, cost  
- Bulk recovery requires explicit review of `PYQ_P2_2_PILOT_REPORT.json`

## Running

```bash
cd apps/backend
python scripts/run_pyq_p2_2_pilot.py
python -m pytest app/modules/cms/tests/test_pyq_p2_2.py -q
```

## Safety gates

- No auto-promote `AI_RECOVERED → VALID`  
- No production DB writes in P2.2  
- `--live` disabled at pilot gate (requires separate authorization)  
- Diagram-dependent questions route to human review  

## Success criteria

Primary metrics:

- Source fidelity (A/B grades)  
- False recovery rate  
- Verification rate  
- Boundary integrity  
- Provenance completeness  

A question that cannot be safely recovered remains PARTIAL.
