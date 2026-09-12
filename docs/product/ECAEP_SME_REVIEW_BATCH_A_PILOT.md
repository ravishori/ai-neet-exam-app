# ECAEP SME Review — Batch A Pilot (WAVE-P0-10)

**Status:** Pilot queue prepared (read-only selection). Human SME is final authority.  
**Database audited:** `trinetra_db` (development). No production writes.  
**Pilot ID:** `batch-a-sme-pilot-40`  
**Batch ID:** `acquisition-batch-A-diversify-p0` (`model_used=human-authored-batch-a`)

This wave **prepares and supports** human review. It does **not** certify scientific correctness, approve, or publish questions.

---

## Absolute rules (unchanged)

- No auto-approve / auto-publish / bulk approve / bulk publish
- Checklist completion alone does **not** approve
- Publishing remains a separate explicit action (WAVE-P0-4 gates stay active)
- Provenance stays truthful: **Human-authored Batch A** — **SME review required** — not official NTA/NCERT
- Student surfaces: **PUBLISHED only**
- Quality over campaign targets (“review 40; publish only what passes”)

---

## Inventory (read-only audit)

| Item | Result |
|------|--------|
| Batch A questions identified | **74** |
| Current status (all 74) | **DRAFT** |
| Pilot selected | **40** |
| Remaining Batch A untouched | **34** (still DRAFT; not in pilot filter) |

Provenance on Batch A: `model_used=human-authored-batch-a`, tags include batch id, `origin:human-authored`, `not-official-nta`, `sme-review-required`.

---

## Pilot subject distribution

| Subject | Pilot count |
|---------|------------:|
| Physics | 10 |
| Chemistry | 10 |
| Botany | 10 |
| Zoology | 10 |

Selection priority applied: structurally valid → mapped → known provenance → chapter/topic/difficulty diversity. Not “first 40.”

### Chapter distribution (pilot)

| Chapter | Count | Notes |
|---------|------:|-------|
| Electrostatics | 5 | Physics |
| Optics | 5 | Physics |
| Equilibrium | 5 | Chemistry |
| Organic Chemistry - Basic Principles | 5 | Chemistry |
| Cell - The Unit of Life | 10 | **Only Batch A Botany chapter** — unavoidable for this pilot |
| Animal Kingdom | 4 | Zoology priority |
| Biomolecules | 3 | Zoology |
| Human Reproduction | 3 | Zoology |

### Difficulty (before human review)

| Difficulty | Count |
|------------|------:|
| Easy | 23 |
| Medium | 13 |
| Hard | 4 |

Reviewers may override difficulty only via normal content editing — **not** auto-modified by this wave.

---

## How the reviewer works

1. Open **Admin → Editorial Review** (`/admin/ai-review`)
2. Defaults: **Batch A pilot (~40)** + **Batch A only** + status **DRAFT**
3. Or API: `GET /api/v1/cms/editorial-batch-a-pilot` (read-only roster)
4. Or queue: `GET /api/v1/cms/editorial-review-queue?status=DRAFT&pilot_only=true`
5. Open each item → review packet (stem, options, answer, explanation, mapping, provenance)
6. Workflow (existing ECAEP — no parallel path):

```
DRAFT → submit → IN_REVIEW → approve | request_changes → APPROVED → publish → PUBLISHED
```

7. Record concise review notes when useful (editorial-only; not student-facing unless product already defines otherwise)

### Review checklist (A–I)

| ID | Criterion |
|----|-----------|
| A | Scientific correctness |
| B | Exactly one defensibly correct answer |
| C | Distractors plausible and unambiguous |
| D | NEET suitability |
| E | NCERT / syllabus alignment |
| F | Explanation accurate and clear |
| G | Academic mapping correct |
| H | Difficulty appropriate |
| I | Provenance accurate (+ Batch A / source verification items) |

If no authoritative source was checked: mark **Source verification required**. Do not invent citations.

---

## Selected pilot roster (trinetra_db)

Order below is the recommended review order (interleaved Physics chapter diversity first, then Chemistry, Botany, Zoology — Zoology prioritized for coverage without quality compromise).

| Label | Subject | Chapter | Topic | Diff | Title | ID |
|-------|---------|---------|-------|------|-------|----|
| PHY-01 | Physics | Electrostatics | Capacitance | easy | Capacitance formula | `8721e193-2d6e-433a-81d9-ceb2b31aef01` |
| PHY-02 | Physics | Optics | Reflection and Mirrors | easy | Concave mirror focus | `f51bd10d-70c1-4bc1-98f3-490f723ec549` |
| PHY-03 | Physics | Electrostatics | Capacitance | medium | Dielectric effect | `fbfa14ed-b9cc-4016-8c4b-d08f997ecdd6` |
| PHY-04 | Physics | Optics | Reflection and Mirrors | easy | Mirror formula relation | `4d0ab71e-a997-4ac1-ad17-ba24f030a19c` |
| PHY-05 | Physics | Electrostatics | Capacitance | hard | Energy stored | `f7b0f62f-1fcb-4a69-9052-455e00f7cb84` |
| PHY-06 | Physics | Optics | Reflection and Mirrors | easy | Focal length and radius | `9a0ae17f-38f3-4141-8dad-389ae265195c` |
| PHY-07 | Physics | Electrostatics | Electric Charge and Coulomb's Law | easy | Coulomb force direction | `4b928b5f-da43-4361-89db-312b6c6950a4` |
| PHY-08 | Physics | Optics | Refraction and Lenses | easy | Refractive index | `6d7b9e60-e56f-46e0-b553-654aba9c4a47` |
| PHY-09 | Physics | Electrostatics | Electric Charge and Coulomb's Law | easy | Coulomb force distance dependence | `961327ff-e291-4c57-a5c2-4f2de51f9004` |
| PHY-10 | Physics | Optics | Refraction and Lenses | medium | Convex lens power | `18238e36-2102-4aea-acca-9c9709d0722e` |
| CHE-01 | Chemistry | Equilibrium | Chemical Equilibrium | easy | Dynamic equilibrium | `c284bfd6-c783-4098-a41d-b4322bcd1bba` |
| CHE-02 | Chemistry | Organic Chemistry - Basic Principles | Electronic Effects | medium | Inductive effect | `8e8d2c35-6ce6-4d31-a900-bbc2d9256fc7` |
| CHE-03 | Chemistry | Equilibrium | Chemical Equilibrium | easy | Kc expression | `e0ec2129-93c2-4d6d-b8a2-51ef001d25df` |
| CHE-04 | Chemistry | Organic Chemistry - Basic Principles | Electronic Effects | medium | Resonance | `69358bd6-f96e-4ade-8d3e-15b56765e784` |
| CHE-05 | Chemistry | Equilibrium | Chemical Equilibrium | medium | Le Chatelier temperature | `ae94b0ff-dab5-466e-9679-176c3ed999a5` |
| CHE-06 | Chemistry | Organic Chemistry - Basic Principles | Electronic Effects | hard | Electron withdrawing group | `11dc1fa4-5f8d-49d3-960a-cbdaaa2fae9e` |
| CHE-07 | Chemistry | Equilibrium | Ionic Equilibrium and pH | easy | Neutral water pH | `a67f547c-9aea-4e11-aaf2-cdd4a4e7c6d9` |
| CHE-08 | Chemistry | Organic Chemistry - Basic Principles | IUPAC and Homologous Series | easy | Homologous difference | `dfefa603-2b3d-42d6-87d9-6824dfebb472` |
| CHE-09 | Chemistry | Equilibrium | Ionic Equilibrium and pH | easy | Acidic pH | `9c152f29-fabe-4e57-990a-33aa497282d6` |
| CHE-10 | Chemistry | Organic Chemistry - Basic Principles | IUPAC and Homologous Series | easy | Alkane general formula | `786c5fe7-a99b-4989-a9ff-b39d5804f7aa` |
| BOT-01 | Botany | Cell - The Unit of Life | Cell Organelles | easy | Mitochondria function | `74b66e54-2b13-4603-8f83-cb31b3f43f2c` |
| BOT-02 | Botany | Cell - The Unit of Life | Cell Organelles | easy | Chloroplast pigment | `15fedcb1-c5bb-48a0-b8f9-d9d2d6fa8e7d` |
| BOT-03 | Botany | Cell - The Unit of Life | Cell Organelles | medium | Endosymbiotic clue | `9a751a08-7519-4c59-9780-9202b1f52874` |
| BOT-04 | Botany | Cell - The Unit of Life | Cell Theory and Cell Types | easy | Prokaryote nucleus | `bb309256-11ab-46ea-8027-4e8613c55e39` |
| BOT-05 | Botany | Cell - The Unit of Life | Cell Theory and Cell Types | easy | Cell theory | `c6da7942-613f-43ec-ad9f-04ca3271fd9b` |
| BOT-06 | Botany | Cell - The Unit of Life | Cell Theory and Cell Types | medium | Plant cell wall | `167f3263-3eca-4f2a-b15c-63baa8099f86` |
| BOT-07 | Botany | Cell - The Unit of Life | Membrane and Cell Cycle | easy | Selective permeability | `37d93e81-39b9-478f-8879-eadcdc14c264` |
| BOT-08 | Botany | Cell - The Unit of Life | Membrane and Cell Cycle | easy | Ribosome site | `5dfc15b6-f80a-46e0-8ce4-026e91fbc473` |
| BOT-09 | Botany | Cell - The Unit of Life | Membrane and Cell Cycle | medium | Fluid mosaic model | `b03be959-23f9-44ec-a16c-9a59aa757fc1` |
| BOT-10 | Botany | Cell - The Unit of Life | Cell Organelles | hard | Golgi function | `ba13a30e-d7b9-4f35-8271-b867432ebe64` |
| ZOO-01 | Zoology | Animal Kingdom | Basis of Classification | easy | Radial symmetry | `f7d2d624-b7fd-4a5f-be51-b4ead085a448` |
| ZOO-02 | Zoology | Biomolecules | Carbohydrates and Lipids | easy | Carbohydrate monomer | `eadb0cd4-b86a-40a5-9c18-38ca2f77a1c2` |
| ZOO-03 | Zoology | Human Reproduction | Gametogenesis | medium | Spermatogenesis site | `c0a62141-f609-4bf5-97e8-3777dae6fd25` |
| ZOO-04 | Zoology | Animal Kingdom | Basis of Classification | medium | Tissue grade | `b4bcc4fb-b21d-495d-b8a9-0dce2bcd0bf6` |
| ZOO-05 | Zoology | Biomolecules | Carbohydrates and Lipids | medium | Glycogen | `ca107949-55bb-4f47-bc05-84b10f4c0205` |
| ZOO-06 | Zoology | Human Reproduction | Gametogenesis | medium | Polar bodies | `b932a1a7-0262-4381-b726-ee632e01e6c8` |
| ZOO-07 | Zoology | Animal Kingdom | Basis of Classification | hard | Coelom | `391fa796-0af0-4a45-910a-8bfd6946d251` |
| ZOO-08 | Zoology | Biomolecules | Nucleic Acids | easy | DNA sugar | `56ee4f23-2bae-4f14-b25c-c1d9e90c2fd1` |
| ZOO-09 | Zoology | Human Reproduction | Male and Female Reproductive Systems | easy | Male gonad | `d8434de2-aa82-4ab4-8f2d-a15a044d8169` |
| ZOO-10 | Zoology | Animal Kingdom | Chordata Basics | medium | Notochord | `0bc07e86-5546-4115-ab47-12d31e335afe` |

Live roster (same selection logic): `GET /api/v1/cms/editorial-batch-a-pilot` with `content.review`.

---

## Post-pilot metrics (fill after human campaign)

| Metric | Result |
| ----------------------- | -----: |
| Physics reviewed | |
| Chemistry reviewed | |
| Botany reviewed | |
| Zoology reviewed | |
| Approved | |
| Returned for changes | |
| Rejected | |
| Published | |
| Average difficulty | |
| Provenance verified | |
| Mapping corrections | |
| Explanation corrections | |
| Scientific issues found | |

A low approval rate is **not** failure — it may mean acquisition quality needs improvement.

---

## Security / RBAC

| Action | Permission |
|--------|------------|
| View pilot / queue / packet | `content.review` |
| Submit DRAFT → IN_REVIEW | content workflow (creator / authorized) |
| Approve / request changes | `content.review` |
| Publish | `content.publish` (existing gates) |
| Students | No review APIs; practice = PUBLISHED only |

---

## Auditability

Existing review/publish audit path records question id, reviewer, action, timestamps, status transitions, decision, and notes. No secrets / student PII in editorial logs.

---

## Acceptance (WAVE-P0-10)

- [x] 40-question pilot queue prepared (10/10/10/10)
- [x] Remaining 34 Batch A untouched by this wave
- [x] Reviewer can identify pilot via UI filters / API
- [x] Review packet includes Batch A labels + SME checklist
- [x] No auto-approve / auto-publish / bulk publish
- [x] Publishing gates unchanged
- [x] Provenance truthful
- [x] Tests for selection + read-only pilot endpoint

---

## Recommended next wave

After humans complete the 40-question pilot and fill metrics above:

1. Evaluate process (approval rate, scientific issues, mapping/explanation corrections)
2. Only then open the remaining **34** Batch A items (or refine acquisition)
3. Optional: acquire additional Botany chapters (Cell-only constraint in Batch A)
4. Continue Zoology carefully — grow published base without monoculture pressure
