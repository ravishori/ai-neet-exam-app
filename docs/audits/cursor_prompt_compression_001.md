# CURSOR-PROMPT-COMPRESSION-001

**Generated:** 2026-09-14  
**Mode:** documentation / rules architecture only  
**Verdict:** **YELLOW**

## Summary

Permanent TALOS content-safety policy was centralized into a compact `.cursor/rules/` hierarchy plus `docs/architecture/cursor_task_protocol.md`. Existing NEET-2026 syllabus boundary was **preserved unchanged**. No application code or database mutations.

## Files inspected

- `.cursor/rules/neet-2026-syllabus-boundary.mdc`
- `.cursor/rules/studymaterial-archive.mdc`
- `.cursorrules`
- `.cursor/CURSOR_RULES.md`, `.cursor/README.md` (index / enterprise docs)
- `docs/architecture/ncert_canonical_source.md`
- `docs/architecture/ecaep.md` (referenced for safety posture)
- Recent audits under `docs/audits/` (pattern source for protocol)

## Files created

| Path | Purpose |
|------|---------|
| `.cursor/rules/project-core.mdc` | Accuracy / verification / source honesty |
| `.cursor/rules/ncert-source-boundary.mdc` | Canonical `NCERT Books/` factual root |
| `.cursor/rules/content-safety.mdc` | No generate/publish/provider by default |
| `.cursor/rules/content-factory.mdc` | CMS pipeline (glob-scoped) |
| `.cursor/rules/mcq-quality.mdc` | MCQ quality bar (glob-scoped) |
| `.cursor/rules/database-safety.mdc` | Surgical DB / measured counts |
| `.cursor/rules/audit-protocol.mdc` | Audit cadence + artifact authority |
| `.cursor/rules/README.md` | Rule map index |
| `docs/architecture/cursor_task_protocol.md` | Compact task template + compression guidance |
| `docs/audits/cursor_prompt_compression_001.md` | This audit |
| `docs/audits/cursor_prompt_compression_001.json` | Machine-readable audit |

## Files modified

- None of the pre-existing always-on safety rules were edited.
- Application / DB / blueprint / KU / question code: **untouched**.

## Rules consolidated

Permanent policies repeatedly pasted into recent content-factory tasks (syllabus, NCERT root, no fuzzy authorize, no silent provenance upgrade, measure before/after, surgical writes, audit artifacts, no generate unless authorized) are now covered by the new always-on / glob-scoped rules plus the task protocol.

## Duplicate rules identified

| Item | Assessment |
|------|------------|
| `neet-2026-syllabus-boundary.mdc` mentions NCERT Books briefly; `ncert-source-boundary.mdc` expands the same root | Complementary (depth), not conflicting |
| `studymaterial-archive.mdc` vs NCERT factual root | Complementary scopes: archive discovery ≠ generation evidence |
| Root `.cursorrules` (“5000 Class 11 Physics MCQ Generator”) vs TALOS modular monolith | **Legacy narrow scope remains**; not deleted. Future cleanup candidate |
| Large `.cursor/CURSOR_RULES.md` / enterprise tree vs compact `.cursor/rules/*.mdc` | Compatibility duplication remains for older workflows |

## Conflicts identified

- **None that weaken syllabus or NCERT boundaries.**
- Non-blocking tension: root `.cursorrules` still describes a Physics-5000 generator role while CLAUDE.md / product docs describe TALOS modular monolith. Left unresolved (STOP-if-conflict applies to safety boundary conflicts; this is scope drift, flagged for future cleanup).

## Safety boundaries preserved

- `neet-2026-syllabus-boundary.mdc` intact (dual gates, no fuzzy authorize, pipeline order).
- NCERT factual root remains `NCERT Books/` only; StudyMaterial explicitly non-substitutable.
- Content-safety defaults: no generate/publish/provider unless authorized.
- No rule text was weakened relative to prior always-on syllabus rule.

## Estimated prompt-token reduction

Not precisely measured. Approximate example using recent task class `NCERT-EVIDENCE-WRITE-002`:

| Form | Approx. scale |
|------|----------------|
| Verbose prompt (full safety essays + pasted IDs + hard-coded counts) | ~3–6k+ tokens typical |
| Compressed protocol (READ audit JSON + ALLOWED/VERIFY/OUTPUT) | ~200–400 tokens |

**Rough reduction:** often **>50%** for remediation-style tasks when IDs/counts stay in audit JSON and policy stays in rules. Not a universal percentage.

## Tests run

- `tests/test_syllabus_gate_001.py` + `tests/test_mcq_ncert_grounding_001.py` → **37 passed**

(Documentation-only change; no app behavior expected.)

## Failures / warnings

- None for rule content.
- YELLOW because: (1) legacy `.cursorrules` / large `.cursor/` tree still duplicate some guidance; (2) token reduction is estimated, not instrumented.

## Limitations

- Did not rewrite or delete the enterprise `.cursor/` documentation tree.
- Did not modify root `.cursorrules` (legacy Physics-5000 framing) to avoid silent policy replacement.
- Did not commit or push.
