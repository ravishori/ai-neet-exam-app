# P5 AMBER Remediation — Full 95 Diversity Forensics

**Verdict:** `AMBER — LIMITED QUALITY/DIVERSITY REMEDIATION REQUIRED`  
**Captured:** 2026-09-02T17:07:02.358703+00:00  
**Scope:** READ-ONLY (no DB mutations, no LLM calls)

## A. Population
```text
95 P4-GREEN DRAFTs
batch: factory-p3-pilot-2026-09-01-batch (22c5684b-…)
excluded: 5 older CREATED; smoke DRAFT; legacy; T6-D; T6-F2; unrelated factory
```

## B. Diversity findings (item primary labels)
```text
EXACT_DUPLICATE: 0
NORMALIZED_DUPLICATE: 0
NEAR_DUPLICATE: 30
SAME_TEMPLATE_REPETITION: 47
LEGITIMATE_CONCEPTUAL_OVERLAP: 17
UNCERTAIN: 0
UNIQUE: 1
```
Pair counts (forensic edges): `{'NEAR_DUPLICATE': 44, 'LEGITIMATE_CONCEPTUAL_OVERLAP': 254, 'SAME_TEMPLATE_REPETITION': 144}`  
Machine candidates screened: 442

## C. Cluster summary
- **C01** n=10 | Zoology / Blood and Blood Groups | SAME_TEMPLATE_REPETITION | items=075b8e7a, 1688d0d2, 1da3cbb7, 57971e98, 5eb8f972, 6933c286, 8abbb607, 9c16dac8, c9effada, cf312a49 | p5=['c9effada-d968-42cb-9f79-bba0a221030e']
- **C02** n=10 | Botany / Light Reaction | SAME_TEMPLATE_REPETITION | items=17d55439, 196ca9b0, 25575939, 411e52ae, 49052063, 4e09c002, 610ac645, 6b33d68c, ac0e21a2, b949be80 | p5=['49052063-51a8-4e92-b970-fa2c163bc225']
- **C03** n=8 | Physics / Electric Current and Ohm's Law | SAME_TEMPLATE_REPETITION | items=14d5b9ce, 211df873, 2c9a9a28, 5502fd26, 62f0679e, 640043ef, b9e207cf, c97a1c08 | p5=['5502fd26-32e0-4d3d-bc49-2fcfded63006']
- **C04** n=7 | Physics / Electric Current and Ohm's Law | SAME_TEMPLATE_REPETITION | items=549a8607, 754c8048, 94046277, d237ea98, e08487f5, e5dffeb7, e64bab8b | p5=[]
- **C05** n=5 | Chemistry / Ionic Bonding | SAME_TEMPLATE_REPETITION | items=06f482fd, 27d37116, 41b5452c, a91371a7, bd3a9ae0 | p5=[]
- **C06** n=5 | Zoology / Blood and Blood Groups | SAME_TEMPLATE_REPETITION | items=14f37b63, 1ff41f0a, 339e432c, aa288e3f, d290c7a6 | p5=[]
- **C07** n=5 | Chemistry / Ionic Bonding | NEAR_DUPLICATE | items=574bb5d6, 851ad68b, 8704a88f, 8d424bd3, e1b6c7fe | p5=[]
- **C08** n=5 | Chemistry / Ionic Bonding | NEAR_DUPLICATE | items=4de4ceaf, d1a53096, dac3ca87, e33bce0c, eb74936c | p5=[]
- **C09** n=4 | Physics / Electric Current and Ohm's Law | NEAR_DUPLICATE | items=12e1d3fd, 6aae8050, c63c00be, e19e4ad1 | p5=['c63c00be-61ad-49f6-99a3-7b5f10a3daf7', 'e19e4ad1-f881-4864-bb82-3d4cf4126647']
- **C10** n=2 | Physics / Electric Current and Ohm's Law | NEAR_DUPLICATE | items=00b45e3d, 4385d426 | p5=[]
- **C11** n=2 | Botany / Light Reaction | NEAR_DUPLICATE | items=00ea201f, 8def0aaa | p5=[]
- **C12** n=2 | Physics / Electric Current and Ohm's Law | NEAR_DUPLICATE | items=10ed5382, e122280b | p5=[]
- **C13** n=2 | Physics / Electric Current and Ohm's Law | NEAR_DUPLICATE | items=14146a50, 6fde7ec4 | p5=[]
- **C14** n=2 | Chemistry / Ionic Bonding | NEAR_DUPLICATE | items=31959259, a7f6bf5c | p5=[]
- **C15** n=2 | Physics / Electric Current and Ohm's Law | SAME_TEMPLATE_REPETITION | items=52a054bd, 5bd533ce | p5=[]
- **C16** n=2 | Physics / Electric Current and Ohm's Law | NEAR_DUPLICATE | items=55fb1405, a4fb3d3a | p5=[]
- **C17** n=2 | Physics / Electric Current and Ohm's Law | NEAR_DUPLICATE | items=9caadfac, cb9a84a7 | p5=[]
- **C18** n=2 | Botany / Light Reaction | NEAR_DUPLICATE | items=9f14655e, d75d0dee | p5=[]

## D. Subject summary
```text
{
  "Physics": {
    "n": 40,
    "labels": {
      "NEAR_DUPLICATE": 14,
      "SAME_TEMPLATE_REPETITION": 17,
      "LEGITIMATE_CONCEPTUAL_OVERLAP": 9
    },
    "unique": 0,
    "near_duplicates": 14,
    "same_template_repetitions": 17,
    "exact_or_normalized": 0,
    "legitimate_conceptual_overlap": 9,
    "uncertain": 0
  },
  "Botany": {
    "n": 20,
    "labels": {
      "NEAR_DUPLICATE": 4,
      "LEGITIMATE_CONCEPTUAL_OVERLAP": 6,
      "SAME_TEMPLATE_REPETITION": 10
    },
    "unique": 0,
    "near_duplicates": 4,
    "same_template_repetitions": 10,
    "exact_or_normalized": 0,
    "legitimate_conceptual_overlap": 6,
    "uncertain": 0
  },
  "Chemistry": {
    "n": 20,
    "labels": {
      "SAME_TEMPLATE_REPETITION": 5,
      "NEAR_DUPLICATE": 12,
      "LEGITIMATE_CONCEPTUAL_OVERLAP": 2,
      "UNIQUE": 1
    },
    "unique": 1,
    "near_duplicates": 12,
    "same_template_repetitions": 5,
    "exact_or_normalized": 0,
    "legitimate_conceptual_overlap": 2,
    "uncertain": 0
  },
  "Zoology": {
    "n": 15,
    "labels": {
      "SAME_TEMPLATE_REPETITION": 15
    },
    "unique": 0,
    "near_duplicates": 0,
    "same_template_repetitions": 15,
    "exact_or_normalized": 0,
    "legitimate_conceptual_overlap": 0,
    "uncertain": 0
  }
}
```

## E. P5 known findings
```text
[
  {
    "item_id": "49052063-51a8-4e92-b970-fa2c163bc225",
    "p5_finding": "near-duplicate",
    "template_family_size": 10,
    "cluster_size": 10,
    "full_population_status": "systematic pattern"
  },
  {
    "item_id": "5502fd26-32e0-4d3d-bc49-2fcfded63006",
    "p5_finding": "near-duplicate",
    "template_family_size": 8,
    "cluster_size": 8,
    "full_population_status": "systematic pattern"
  },
  {
    "item_id": "c63c00be-61ad-49f6-99a3-7b5f10a3daf7",
    "p5_finding": "near-duplicate",
    "template_family_size": 4,
    "cluster_size": 4,
    "full_population_status": "systematic pattern"
  },
  {
    "item_id": "e19e4ad1-f881-4864-bb82-3d4cf4126647",
    "p5_finding": "near-duplicate",
    "template_family_size": 4,
    "cluster_size": 4,
    "full_population_status": "systematic pattern"
  },
  {
    "item_id": "c9effada-d968-42cb-9f79-bba0a221030e",
    "p5_finding": "ambiguity / poor explanation",
    "template_family_size": 10,
    "cluster_size": 10,
    "full_population_status": "expanded cluster"
  }
]
```

## F. Rh ambiguity
```text
systemicity: repeated pattern
stored_answer_affected: False
similar_pattern_count: 3
```

## G. P4 assessment
Gate F uses exact/normalized/option-stem fingerprints only (`SEMANTIC_DEDUPE_NOT_AVAILABLE`).  
Near-duplicate / same-template pairs generally show **P4 Gate F correctly passed under implemented definition**.

## H. Systemicity
```text
SYSTEMIC_DIVERSITY_RISK
```

## I. Root cause
```text
MULTIPLE
```

## J. Minimum remediation
Minimum effective: B+C — (B) diversify subject blueprints beyond single-concept slices (Chemistry Lattice Energy; Physics Ohm stretch/voltage templates; Botany non-cyclic; Zoology ABO sequence); (C) add in-slice anti-paraphrase / prior-stem diversity constraints at generation. Secondary: limited E for Rh phenotype↔explanation completeness (3/95). Supporting later: D semantic near-dupe detection (Gate F exact/normalized behaved as designed).

## K. Integrity
```text
questions changed: 0
options changed: 0
answers changed: 0
explanations changed: 0
blueprints changed: 0
statuses changed: 0
legacy changed: false
T6-D changed: false
T6-F2 changed: false
protected published changed: false
unexpected mutations: []
body_fp unchanged: True
```

## L. Final forensic verdict
```text
AMBER — LIMITED QUALITY/DIVERSITY REMEDIATION REQUIRED
```

## M. Next gate
```text
NEXT: targeted remediation design
```

STOP. No content or code changes were made.
