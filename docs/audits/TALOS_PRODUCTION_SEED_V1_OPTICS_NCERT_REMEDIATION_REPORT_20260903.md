# Production Seed V1 — Optics NCERT Part-II Remediation

**Final verdict:** `GREEN — OPTICS NCERT EVIDENCE RESOLVED`

```text
CERTIFIED = YES
ALLOWLIST_READY = YES
APPROVAL_PREFLIGHT = PASS
APPROVED = 0
PUBLICATION = NO
ECAEP = 0
```

## Executive Verdict
```text
GREEN — OPTICS NCERT EVIDENCE RESOLVED
```

## Source Acquisition
```text
official source identified = YES
official PDF acquired = YES
document identity verified = YES
sha256 = 5c9570cc9f45cbe8f8d62100ccecd3370f8d8085f57041764bd1940bf467d235
registered in StudyMaterial = YES
StudyMaterial.zip had Part-II = NO (Part-I only)
source_url = https://ncert.nic.in/textbook/pdf/leph201.pdf
```

## Target Question
```text
item_id = 3d0dbda5-7882-4e3f-90d8-3a479cf67ab2
subject = Physics
class = 12
chapter = Optics / Ray Optics and Optical Instruments
topic = Refraction and Lenses
stored_answer = B (30 cm)
independent_answer = B
answer_match = True
```

## Evidence
```text
previous = missing_evidence
new = SOURCE_TEXT_VERIFIED
section = 9.4 Thin lenses / Thin lens formula (Ray Optics and Optical Instruments)
page_number = null
page_verified = false
source_excerpt = ngle spherical surface and follow it by thin lenses. A thin lens is a transparent optical medium bounded by two surfaces; at least one of which should be spherical. Applying the formula for image form...
```
Evidence supports the thin-lens formula used by the question (`1/v − 1/u = 1/f`) from official NCERT Class XII Physics Part-II, Chapter Nine.

## Runtime Gates
```text
NCERT evidence gate = PASS
content gates (if APPROVED) = PASS
full publish if APPROVED = True
review gate as DRAFT = NOT_APPROVED (expected)
```

## Exact-30 Result
```text
READY_FOR_APPROVAL = 30
BLOCKED = 0
```

## Protected / integrity
```text
protected_mutations = []
other_29 evidence unchanged = YES
stem/options/answer/explanation changes = 0
DRAFT = 30; APPROVED = 0; PUBLISHED = 0
```

## Tests
```text
tests_run = ['test_physics_t6d_pilot','test_physics_t6f2_publish','test_content_factory_p4']
tests_passed = 11
tests_failed = 0
```

## STOP
No approve · no publish · no ECAEP · no replacements.
Next separate task only if READY_FOR_APPROVAL = 30: `PRODUCTION SEED V1 — APPROVE EXACT 30`.
