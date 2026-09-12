# Production Seed V1 — Publication Authorization (Dry-Run)

**Final verdict:** `GREEN — EXACT-30 PUBLICATION AUTHORIZATION PACKAGE READY`
**Publication executed:** `NO`
**Approved mutations:** `0` · **Published mutations:** `0` · **ECAEP:** `0`

```text
CERTIFIED = YES
ALLOWLIST_READY = YES
PUBLICATION = NO
```

## Executive Verdict
```text
GREEN — EXACT-30 PUBLICATION AUTHORIZATION PACKAGE READY
```
This is an authorization **package** for review. It is **not** permission to publish and does **not** publish.

## Exact cohort
```text
Expected = 30
Actual = 30
```

### Exact UUID allowlist (canonical order)

01. `1d598d79-afe1-4ddb-8f32-2b51c8fb2b02`
02. `e15d0065-7b79-477c-b9ec-81bc421a6a71`
03. `7e4fb145-08fe-43cf-accc-ef53e9535b07`
04. `c85bba09-451b-4b2f-988d-e440929fa770`
05. `f6f59a22-5d9b-47a3-adb6-8dcf7ce56a1c`
06. `93c46e39-6a4c-4730-9ae7-a07a4bdab0a9`
07. `aae4fe1b-9665-4216-be4b-2f758f4dbf70`
08. `4f0dcbb1-c236-42a3-a148-cf8233326b52`
09. `18f304f5-89b2-4bcb-a4dd-b04eb6374cad`
10. `3c565dee-ea37-4937-bb32-4006ce383006`
11. `e3e36b8e-ff15-455e-807d-eb32de6c1f75`
12. `621ffc10-0673-4d4f-a5be-c07ed2f7f48f`
13. `5b1b5f27-bb6d-4b35-8b1c-96c252278d98`
14. `9dd374e7-c677-46ab-9e83-8cf0e6139feb`
15. `a357fe24-b0ef-4bd5-b7f7-956f392f9942`
16. `e4a6fdc3-7a55-4762-a176-f8af33709308`
17. `336ec42d-aa33-4b5b-8c46-f8d5461883b0`
18. `27552790-48f4-48ba-bc37-fdbd14902dfb`
19. `16dd7280-a48b-4437-80ac-a2b72b28d952`
20. `872a0115-cb0a-4109-99ff-55ada6774d51`
21. `b4a2e055-f141-4f05-8b06-850d84122b60`
22. `3d0dbda5-7882-4e3f-90d8-3a479cf67ab2`
23. `92c31281-cbdf-4954-9b25-79342cb1b400`
24. `b207ad06-7427-417e-abfd-a928ab68df84`
25. `061d07ed-ca1f-4f31-b7f8-cbdb3dfe8453`
26. `b690c0d3-98f6-4e57-851f-aae1ac6ad8cd`
27. `8a3937ce-5ad0-41af-bc84-17bf04c386ce`
28. `2e17c7e6-5d8f-4469-9cea-407177e61e8e`
29. `3dc11d2a-b9ad-4155-93ec-4cd7b3bae9af`
30. `dd7b5422-437d-4b0f-a2dc-f370ea0496c2`

**allowlist_sha256** = `c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1`

**Ordering:** subject(Botany,Chemistry,Physics,Zoology), chapter, topic, item_id

## Subject distribution
```text
Physics = 10
Chemistry = 10
Botany = 5
Zoology = 5
Total = 30
```

## Certification
```text
P4 = 30/30 GREEN
Diversity = {'UNIQUE': 30}
Human review = retained historical ACCEPT + replacement ACCEPT (provisional factory review)
NCERT = 30 CERTIFIED_WITH_LIMITATION (page_verified=false)
Answer MATCH = 30/30
```

## NCERT page limitation
```text
NCERT limitation acknowledged
page_verified = false for all 30
No page numbers invented
Content-certification DoD permits CERTIFIED_WITH_LIMITATION without page-level evidence
Runtime publish gate: 30/30 bodies lack structured ncert_evidence — must be addressed in future PUBLISH EXACT 30 execution (SECTION_VERIFIED/SOURCE_TEXT_VERIFIED), not by inventing pages
```

## Historical exclusions
```text
a1f1d832-21a3-4fb6-86b8-fe07ed46ad18
→ EXCLUDED
→ historical FAIL
→ replacement 27552790-48f4-48ba-bc37-fdbd14902dfb
54907eea-4fcd-4855-8477-268bafe03e82
→ EXCLUDED
→ historical HUMAN_REVIEW
→ replacement 18f304f5-89b2-4bcb-a4dd-b04eb6374cad
```

## Cross-cohort exclusions
```text
previous 95 overlap = 0
T6-D overlap = 0 (population 100)
T6-F2 overlap = 0 (population 938)
legacy overlap = 0 (population 5000)
historical rejected overlap = 0
seed batch CREATED = 32; not in allowlist (rejected originals) = 2
DRAFT total ≈ 5281; publishable_exact_allowlist = 30; other_DRAFTs_excluded = 5251
APPROVED = 0; PUBLISHED questions = 1049
```

### Protected population fingerprints (preflight)
```text
T6-D content_fp = e0758fbcb071180b61a33f2b4581e894
T6-F2/T6-F1 content_fp = 17a1672c444c8362ed0261dacf0f82c7
legacy content_fp = 13d51e697382663a28ffc44fd56aedb1
```

## Publication implementation analysis
- Safe target mode: **per-item UUID** `POST /content-items/{item_id}/publish`
- **PUBLICATION IMPLEMENTATION GAP:** no bulk allowlist+hash API; publish requires **APPROVED** first; bodies need structured `ncert_evidence` for gates
- Dangerous if misused: any script that publishes by `status=DRAFT` or `batch_id` alone

## Dry-run simulation
```text
Would target: 30
Would exclude: all other records
Would publish: 0
Would approve: 0
Would ECAEP: 0
```

## Publication firewall / integrity
```text
final 30 status = DRAFT
APPROVED mutations = 0
PUBLISHED mutations = 0
ECAEP = 0
unexpected_mutations = []
```

## Future PUBLISH EXACT 30 contract
See JSON `preconditions.future_execution_contract`. Do not execute now.

## STOP
Artifacts only:
- `TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json`
- `TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_REPORT_20260903.md`

No approve · no publish · no ECAEP · no regeneration · no edits.
