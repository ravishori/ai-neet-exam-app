# MCQ-NCERT-VERIFY-001 — Independent NCERT Verification of OpenAI Benchmark

**Date:** 2026-09-14  
**Status:** COMPLETE (READ-ONLY)  
**Source run:** MCQ-PROVIDER-BENCHMARK-002 (`docs/audits/mcq_provider_benchmark_002_20260914.json`)  
**Provider / model:** OpenAI / `gpt-5-mini`  
**NCERT root (only):** `D:\ravishori\AI Neet Exam App\NCERT Books`  
**DB mutations:** none  
**Certification / publish:** not performed  

## Scope

Verified exactly these five CREATED candidates from Benchmark-002:

| # | candidate_id |
|---|--------------|
| 1 | `519e6ab2-ad02-4726-9342-49e8598a1852` |
| 2 | `8d727dc4-49dc-40a7-815f-a2679d9d78bc` |
| 3 | `bb4a0741-efab-43ff-8317-859bf6e91737` |
| 4 | `a85445fa-db5f-4525-8002-ae8f8c928003` |
| 5 | `4926220c-aab9-4322-b2e1-4ddb1d970707` |

**Excluded:** original 129 pilot candidates; OpenAI smoke `aa41982d-8b25-4dfd-81ce-87c3297d9d49`; any other non-CREATED benchmark attempts.

---

## Aggregate decision

### Counts

| Metric | Value |
|--------|------:|
| Candidates reviewed | 5 |
| NCERT_STRONG | 3 |
| NCERT_ACCEPTABLE | 0 |
| NCERT_PARTIAL | 0 |
| NCERT_UNSUPPORTED | 2 |
| NCERT_CONTRADICTED | 0 |
| NEET_SUITABLE | 3 |
| NEET_REVIEW | 0 |
| NEET_UNSUITABLE | 2 |
| Ambiguous | 0 |
| Numerical | 1 |
| Verification failures | 2 |
| PASS_NCERT_VERIFICATION | 3 |
| PASS_WITH_EDITORIAL_REVIEW | 0 |
| FAIL_NCERT_VERIFICATION | 2 |

### Overall provider recommendation

**RED — PROVIDER CONTENT GATE FAILED**

Three candidates (Physics kinetic temperature; Zoology levels of organisation; Physics work–energy numerical) are strongly NCERT-grounded and NEET-suitable. Two candidates (Chemistry Anfinsen-style denaturation protocol; Botany streptomycin / Streptomyces / secondary-metabolite claims) place **substantial claims that are `NCERT_EVIDENCE_NOT_LOCATED`** inside the keyed “correct” content of the exact canonical PDFs.

This is not a stylistic fail. It is a content-grounding fail for unsupervised extension to the remaining 271-question pilot.

**Provider recommendation:** Keep OpenAI `gpt-5-mini` available for generation, but **do not clear** it for unsupervised NCERT-pilot continuation. Require independent NCERT verification per item and harden prompts/constraints to forbid non-NCERT experimental protocols and named antibiotic/process details absent from the blueprint PDF.

---

## Candidate-by-candidate verification

### 1) `519e6ab2-ad02-4726-9342-49e8598a1852` — Physics / Kinetic Interpretation of Temperature

| Field | Value |
|-------|-------|
| provider / model | openai / gpt-5-mini |
| subject / class | PHYSICS / 11 |
| chapter / topic | Kinetic Theory / Kinetic Theory of an Ideal Gas |
| concept | Kinetic Interpretation of Temperature |
| blueprint_id | `7d36871a-de25-492d-bc88-1ec04849d1e8` |
| concept_id | `22226438-aa4f-4d43-b50c-86128df4ffae` |
| KU | `d837eb9b-a4f2-47f4-81bc-114f80a75b29` |
| NCERT PDF | `...\Class 11\Physics\keph2dd\keph2dd\keph205.pdf` |
| NCERT section/page | §12.4.2 (PDF p.7); Example 12.5 (PDF p.7–8); §12.5 equipartition (PDF p.9) |
| keyed answer | A |
| stem verdict | directly supported |
| option A | NCERT-supported |
| option B | contradicted by NCERT |
| option C | contradicted by NCERT |
| option D | contradicted by NCERT |
| correct-answer verdict | supported; uniquely A |
| explanation verdict | NCERT-supported (minor paraphrase) |
| NCERT classification | **NCERT_STRONG** |
| NEET classification | **NEET_SUITABLE** |
| ambiguity | **NO** |
| final recommendation | **PASS_NCERT_VERIFICATION** |

**Evidence (minimum quotes):**

- Example 12.5: average KE per molecule of any ideal gas (monatomic or diatomic) “is always equal to (3/2) kBT … independent of the nature of the gas.”
- §12.4.2: “average translational kinetic energy of the molecules in the gas.”
- §12.5: monatomic gases have only translational degrees of freedom; diatomic gases also rotate.

**Issues:** none material.

---

### 2) `8d727dc4-49dc-40a7-815f-a2679d9d78bc` — Chemistry / Protein structure levels

| Field | Value |
|-------|-------|
| provider / model | openai / gpt-5-mini |
| subject / class | CHEMISTRY / 12 |
| chapter / topic | Biomolecules / Amino Acids and Proteins |
| concept | Primary, Secondary, Tertiary and Quaternary Structure of Proteins |
| blueprint_id | `9f564c4a-903b-4e7e-9596-f9da5d07cc41` |
| concept_id | `23ec568a-0ce9-4504-a778-393598da02f8` |
| KU | `fc3d722b-641e-402a-a3cd-6e25cab4fc5f` |
| NCERT PDF | `...\Class 12\Chemistry 2\lech2dd\lech205.pdf` |
| NCERT section/page | §10.2.3 Structure (PDF p.13–14); §10.2.4 Denaturation (PDF p.14–15 / printed p.295) |
| keyed answer | A |
| stem verdict | unsupported protocol (Anfinsen-style); only partially related to NCERT denaturation |
| option A | partial core aligns with denaturation; urea/BME/refolding = **NCERT_UNSUPPORTED** |
| option B | contradicted by NCERT (primary remains intact) |
| option C | contradicted by NCERT (secondary destroyed on denaturation) |
| option D | not addressed; conflicts with NCERT denaturation examples |
| correct-answer verdict | keyed A matches denaturation *core*, but stem/agents/refolding not in source |
| explanation verdict | unsupported enrichment (Anfinsen, urea, β-mercaptoethanol mechanisms) |
| NCERT classification | **NCERT_UNSUPPORTED** |
| NEET classification | **NEET_UNSUITABLE** (for NCERT-grounded bank) |
| ambiguity | **NO** (B/C conflict NCERT; failure mode is unsupported stem enrichment) |
| final recommendation | **FAIL_NCERT_VERIFICATION** |

**Located NCERT support:**

- “During denaturation secondary and tertiary structures are destroyed but primary structure remains intact.”
- Secondary structure: α-helix / β-pleated sheet via hydrogen bonding.

**NCERT_EVIDENCE_NOT_LOCATED:** `urea`, `β-mercaptoethanol` / `2-mercaptoethanol`, dialysis/oxidation refolding, Anfinsen’s principle.

**Issues:** Substantial unsupported experimental protocol and explanation enrichment; cannot certify as NCERT-grounded from `lech205.pdf` alone.

---

### 3) `bb4a0741-efab-43ff-8317-859bf6e91737` — Botany / Fermented beverages & antibiotics

| Field | Value |
|-------|-------|
| provider / model | openai / gpt-5-mini |
| subject / class | BOTANY / 12 |
| chapter / topic | Microbes in Human Welfare / Microbes in Household Products and Industrial Products |
| concept | Fermented Beverages and Antibiotics |
| blueprint_id | `ea65866b-ecf3-4ea1-b560-b2533d5f38ac` |
| concept_id | `68ab5c7b-cc6f-4f1e-9ee4-a27294f253f1` |
| KU | `af1f49c5-51cf-4608-8c63-57b3ed4eefcc` |
| NCERT PDF | `...\Class 12\Biology\lebo1dd\lebo108.pdf` |
| NCERT section/page | §8.2.1 Fermented Beverages; §8.2.2 Antibiotics (PDF p.3–5) |
| keyed answer | A |
| stem verdict | partially supported |
| option A | ethanol half NCERT-supported; streptomycin/Streptomyces/secondary metabolites/stationary phase = **NCERT_UNSUPPORTED** |
| option B | not addressed by NCERT; factually problematic |
| option C | contradicted in context (Acetobacter makes acetic acid; not a beverage step) |
| option D | contradicted (yeast for spirits/ethanol, not LAB) |
| correct-answer verdict | keyed A not fully source-supported |
| explanation verdict | unsupported enrichment (secondary metabolites, stationary phase, Streptomyces) |
| NCERT classification | **NCERT_UNSUPPORTED** |
| NEET classification | **NEET_UNSUITABLE** (for NCERT-grounded bank) |
| ambiguity | **NO** |
| final recommendation | **FAIL_NCERT_VERIFICATION** |

**Located NCERT support:**

- `Saccharomyces cerevisiae` … “to produce ethanol”; industrial vessels called fermentors.
- Antibiotic example: Penicillin / *Penicillium notatum*; open prompt to name other antibiotics (sources not given).
- `Acetobacter aceti` of acetic acid (supports rejecting C as beverage process).

**NCERT_EVIDENCE_NOT_LOCATED:** `streptomycin`, `Streptomyces`, `secondary metabolites`, `stationary phase`.

---

### 4) `a85445fa-db5f-4525-8002-ae8f8c928003` — Zoology / Levels of organisation

| Field | Value |
|-------|-------|
| provider / model | openai / gpt-5-mini |
| subject / class | ZOOLOGY / 11 |
| chapter / topic | Animal Kingdom / Basis of Classification |
| concept | Levels of Organisation |
| blueprint_id | `159b2b00-9491-45d0-bd41-51eab481dd06` |
| concept_id | `f5112095-56f7-54d4-b8eb-0a16f50e00e0` |
| KU | `bb63139e-acd9-4ab7-92fc-50bebb7b7093` |
| NCERT PDF | `...\Class 11\Biology\kebo1dd\kebo104.pdf` |
| NCERT section/page | §4.1 (PDF p.1–2); Sycon (p.4–5); Hydra (p.5); Planaria/Platyhelminthes (p.1,6); Earthworm/Annelida (p.7) |
| keyed answer | A |
| stem verdict | directly supported |
| option A | NCERT-supported (Sycon / Porifera → cellular) |
| option B | contradicted (Hydra / Cnidaria → tissue, not organ-system) |
| option C | contradicted (Planaria / Platyhelminthes → organ, not tissue) |
| option D | contradicted (Earthworm / Annelida → organ-system, not cellular) |
| correct-answer verdict | supported; uniquely A |
| explanation verdict | NCERT-supported |
| NCERT classification | **NCERT_STRONG** |
| NEET classification | **NEET_SUITABLE** |
| ambiguity | **NO** |
| final recommendation | **PASS_NCERT_VERIFICATION** |

**Evidence (minimum quotes):**

- “Porifera … cellular level of organisation”; examples include Sycon.
- Coelenterates: “tissue level of organisation”; Hydra as polyp example.
- “organ level is exhibited by members of Platyhelminthes”.
- Annelids: “organ-system level”; example Pheretima (Earthworm).

---

### 5) `4926220c-aab9-4322-b2e1-4ddb1d970707` — Physics / Work–Energy Theorem (numerical)

| Field | Value |
|-------|-------|
| provider / model | openai / gpt-5-mini |
| subject / class | PHYSICS / 11 |
| chapter / topic | Work, Energy and Power / Work and Kinetic Energy |
| concept | Work–Energy Theorem |
| blueprint_id | `321cdf46-7a25-4935-b7aa-d3f83e0bea01` |
| concept_id | `43654d12-df1b-4215-9b72-d32bbe0d7429` |
| KU | `7d9598ac-4b33-4d39-b552-7ebc1aa3e31e` |
| NCERT PDF | `...\Class 11\Physics\keph1dd\keph1dd\keph105.pdf` |
| NCERT section/page | Summary WE theorem (PDF p.16); friction + WE application (PDF p.12) |
| keyed answer | C |
| stem verdict | reasonably derived from NCERT WE theorem + friction work |
| option A | numerically true work by pull only — not ΔK |
| option B | numerically true work by friction only — not ΔK |
| option C | NCERT-supported unique correct (net work = ΔK) |
| option D | contradicted (normal force does no work for horizontal displacement) |
| correct-answer verdict | supported; uniquely C |
| explanation verdict | calculation independently verified |
| NCERT classification | **NCERT_STRONG** |
| NEET classification | **NEET_SUITABLE** |
| ambiguity | **NO** (A/B are true partials but do not answer the stem) |
| final recommendation | **PASS_NCERT_VERIFICATION** |

**Independent calculation (not relying on model explanation):**

- \(W_\text{pull} = 10.0 \times 5.0 = 50.0\,\mathrm{J}\)
- \(f_k = \mu_k mg = 0.20 \times 2.0 \times 9.8 = 3.92\,\mathrm{N}\)
- \(W_f = -3.92 \times 5.0 = -19.6\,\mathrm{J}\)
- \(W_N = 0\) (perpendicular)
- \(W_\text{net} = 30.4\,\mathrm{J} = \Delta K\) → **C**

**NCERT formula support:** “change in kinetic energy of a body is the work done by the net force on the body. \(K_f - K_i = W_\text{net}\).”

**Minor editorial issue only:** stem does not state \(g=9.8\,\mathrm{m/s^2}\) (NCERT sometimes uses 10). With \(g=10\), \(W_f=-20\,\mathrm{J}\), net \(=30\,\mathrm{J}\); C remains uniquely correct.

---

## Separation of failure types

| Type | Findings |
|------|----------|
| Factual / NCERT failures | Chem (#2), Botany (#3): substantial `NCERT_UNSUPPORTED` claims in stem/keyed option/explanation |
| Scientific contradictions in keyed answers | none among the five |
| Ambiguity (second defensible correct) | none |
| Editorial / formatting | Physics WE: optional explicit \(g\); not a gate fail |

---

## Database freeze verification (read-only)

Observed after verification (no writes):

| Protected metric | Expected | Observed | OK |
|------------------|----------:|---------:|:--:|
| PUBLISHED | 1479 | 1479 | ✓ |
| IN_REVIEW | 111 | 111 | ✓ |
| SUPERSEDED | 6 | 6 | ✓ |
| chapters | 56 | 56 | ✓ |
| topics | 192 | 192 | ✓ |
| concepts | 318 | 318 | ✓ |
| knowledge_units | 381 | 381 | ✓ |
| blueprints | 445 | 445 | ✓ |
| unmapped DRAFT (`concept_id IS NULL`) | 5024 | 5024 | ✓ |
| pilot CREATED (mcq-pilot-001) | 129 | 129 | ✓ |
| smoke candidate status | CREATED | CREATED | ✓ |
| five benchmark candidates | CREATED | CREATED | ✓ |

Also: DRAFT total QUESTION items = 5434 (unchanged by this task). ECAEP / jobs / runs / candidates were not mutated. Candidates were **not** certified or published.

Freeze checksum: `96207a0823fbb032225f1be45fed7083`

---

## Tests

1. Candidate IDs match Benchmark-002 `candidate_ids` exactly — **PASS**
2. Only `NCERT Books` PDFs used for evidence — **PASS**
3. StudyMaterial / web / alternate editions not used — **PASS**
4. Read-only freeze query executed; protected counts match — **PASS**
5. No candidate status/content mutation; no certification — **PASS**
6. Reports written:
   - `docs/audits/mcq_ncert_verify_001_20260914.md`
   - `docs/audits/mcq_ncert_verify_001_20260914.json`

---

## STOP

No resume of the remaining 271. No generation. No candidate edits. No certify / approve / publish. No commit / push.
