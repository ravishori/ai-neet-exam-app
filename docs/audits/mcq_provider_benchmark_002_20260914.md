# MCQ-PROVIDER-BENCHMARK-002

**Status:** `GREEN — OPENAI BENCHMARK-002 COMPLETE (5/5 CREATED)`
**Generated:** `2026-09-14T00:39:17.253811+00:00`

Controlled OpenAI 5-candidate NCERT benchmark. **Not** the 400-pilot resume. Prior smoke candidate excluded. 271 remaining **not** resumed.

## Provider / model

- Provider: `openai`
- Model: `gpt-5-mini`
- Routing: `fixed:openai`

## Blueprints (5 distinct)

| # | Subject | Class | Chapter | Concept | Blueprint ID | Blueprint key |
|---|---|---|---|---|---|---|
| 1 | PHYSICS | 11 | Kinetic Theory | Kinetic Interpretation of Temperature | `7d36871a-de25-492d-bc88-1ec04849d1e8` | `bp-create-002-20260913-bp-physics-kinetic-interpretation-temperature-mcq` |
| 2 | CHEMISTRY | 12 | Biomolecules | Primary, Secondary, Tertiary and Quaternary Structure of Proteins | `9f564c4a-903b-4e7e-9596-f9da5d07cc41` | `bp-create-001-20260913-bp-chemistry-protein-structure-levels-mcq` |
| 3 | BOTANY | 12 | Microbes in Human Welfare | Fermented Beverages and Antibiotics | `ea65866b-ecf3-4ea1-b560-b2533d5f38ac` | `bp-create-001-20260913-bp-botany-fermented-beverages-antibiotics-mcq` |
| 4 | ZOOLOGY | 11 | Animal Kingdom | Levels of Organisation | `159b2b00-9491-45d0-bd41-51eab481dd06` | `bp-create-002-20260913-bp-zoology-ak-levels-of-organisation-mcq` |
| 5 | PHYSICS | 11 | Work, Energy and Power | Work–Energy Theorem | `321cdf46-7a25-4935-b7aa-d3f83e0bea01` | `bp-create-002-20260913-bp-physics-work-energy-theorem-mcq` |

## Metrics

- Requested: `5`
- Created: `5`
- Attempted: `7`
- Parse failures: `2` (28.6%)
- Validation failures: `0` (0.0%)
- Duplicate failures: `0` (0.0%)
- Provider failures: `0` (0.0%)
- Retries (extra attempts): `2`
- Structured-output success: `5` (100.0%)
- Avg latency ms: `29116.2`
- Cost USD (estimated sum): `0.027872`

## Candidates

| Candidate ID | Status | Subject | Chapter | Concept | Blueprint | Source path | NCERT verify |
|---|---|---|---|---|---|---|---|
| `310312a6-e9d1-448d-85c6-9e43b0793122` | FAILED_PARSE | PHYSICS | Kinetic Theory | Kinetic Interpretation of Temperature | `bp-create-002-20260913-bp-physics-kinetic-interpretation-temperature-mcq` | `Class 11/Physics/keph2dd/keph2dd/keph205.pdf` | NOT PERFORMED |
| `519e6ab2-ad02-4726-9342-49e8598a1852` | CREATED | PHYSICS | Kinetic Theory | Kinetic Interpretation of Temperature | `bp-create-002-20260913-bp-physics-kinetic-interpretation-temperature-mcq` | `Class 11/Physics/keph2dd/keph2dd/keph205.pdf` | NOT PERFORMED |
| `8d727dc4-49dc-40a7-815f-a2679d9d78bc` | CREATED | CHEMISTRY | Biomolecules | Primary, Secondary, Tertiary and Quaternary Structure of Proteins | `bp-create-001-20260913-bp-chemistry-protein-structure-levels-mcq` | `Class 12/Chemistry 2/lech2dd/lech205.pdf` | NOT PERFORMED |
| `bb4a0741-efab-43ff-8317-859bf6e91737` | CREATED | BOTANY | Microbes in Human Welfare | Fermented Beverages and Antibiotics | `bp-create-001-20260913-bp-botany-fermented-beverages-antibiotics-mcq` | `Class 12/Biology/lebo1dd/lebo108.pdf` | NOT PERFORMED |
| `a85445fa-db5f-4525-8002-ae8f8c928003` | CREATED | ZOOLOGY | Animal Kingdom | Levels of Organisation | `bp-create-002-20260913-bp-zoology-ak-levels-of-organisation-mcq` | `Class 11/Biology/kebo1dd/kebo104.pdf` | NOT PERFORMED |
| `e74d9417-443f-499a-a272-bacb38f23ea3` | FAILED_PARSE | PHYSICS | Work, Energy and Power | Work–Energy Theorem | `bp-create-002-20260913-bp-physics-work-energy-theorem-mcq` | `Class 11/Physics/keph1dd/keph1dd/keph105.pdf` | NOT PERFORMED |
| `4926220c-aab9-4322-b2e1-4ddb1d970707` | CREATED | PHYSICS | Work, Energy and Power | Work–Energy Theorem | `bp-create-002-20260913-bp-physics-work-energy-theorem-mcq` | `Class 11/Physics/keph1dd/keph1dd/keph105.pdf` | NOT PERFORMED |

- CREATED candidate IDs: `['519e6ab2-ad02-4726-9342-49e8598a1852', '8d727dc4-49dc-40a7-815f-a2679d9d78bc', 'bb4a0741-efab-43ff-8317-859bf6e91737', 'a85445fa-db5f-4525-8002-ae8f8c928003', '4926220c-aab9-4322-b2e1-4ddb1d970707']`

## NCERT verification

**NCERT verification status = NOT PERFORMED**

Source/provenance metadata is recorded for subsequent independent verification.

## Database safety

- Pilot CREATED: `129` → `129` (ok=`True`)
- Prior smoke CREATED intact: `True` (`aa41982d-8b25-4dfd-81ce-87c3297d9d49`)
- Hard freeze OK: `True`
- Counted toward 271: `False`
- Published/certified: `False` / `False`

## Tests

- Exit: `0`
```

tests/test_openai_adapter_fix_001.py::test_error_classification_intact
  tests\test_openai_adapter_fix_001.py:197: PytestWarning: The test <Function test_error_classification_intact> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_error_classification_intact():

tests/test_openai_adapter_fix_001.py::test_other_adapters_unchanged_import_surface
  tests\test_openai_adapter_fix_001.py:212: PytestWarning: The test <Function test_other_adapters_unchanged_import_surface> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_other_adapters_unchanged_import_surface():

tests/test_openai_adapter_fix_001.py::test_provider_blocked_still_stops_and_rate_limit_retryable
  tests\test_openai_adapter_fix_001.py:227: PytestWarning: The test <Function test_provider_blocked_still_stops_and_rate_limit_retryable> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_provider_blocked_still_stops_and_rate_limit_retryable():

tests/test_mcq_provider_abstraction_001.py::test_provider_blocked_must_stop_and_not_retry
  tests\test_mcq_provider_abstraction_001.py:155: PytestWarning: The test <Function test_provider_blocked_must_stop_and_not_retry> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_provider_blocked_must_stop_and_not_retry():

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 13 warnings in 0.29s
sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## STOP

Do not resume the 271. Do not generate the 400 pilot. Do not publish/certify/commit/push.
