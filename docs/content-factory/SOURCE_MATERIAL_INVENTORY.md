# Source Material Inventory

**Generated:** 2026-09-01T10:25:25.138637+00:00  
**Mode:** READ-ONLY audit — no generation, no DB mutation  
**StudyMaterial root:** `D:\ravishori\AI Neet Exam App\StudyMaterial`  
**Database:** local `trinetra_db` (SELECT only)

## Executive summary

| Metric | Count |
|--------|------:|
| NEET PDFs on filesystem | 68 |
| Registered `source_documents` | 68 |
| Physics | 20 |
| Chemistry | 19 |
| Biology (filesystem subject root) | 29 |
| Class 11 | 40 |
| Class 12 | 28 |
| Academic-mapped → Botany | 1 |
| Academic-mapped → Zoology | 1 |
| Pilot-ready sources | 4 |
| Ingested sources (≥1 job) | 4 |

## Exclusions (NEET generation universe)

| Category | On filesystem | In DB registry | Action |
|----------|-------------:|---------------:|--------|
| **Mathematics** | 0 | 0 | Excluded — not a NEET subject |
| **Uploads/** scratch | 2 | 0 | Excluded from discovery |
| Stale inventory Maths entries | — | 6 | Historical JSON only; no Maths dir on disk |

Mathematics files are **never deleted or modified** by this audit. They are omitted from all NEET totals.

## Per-document inventory

| ID | Relative path | Subject | Class | Pages | Checksum (prefix) | Registry status | Mapping | Sections | KU (pass) | Pilot ready | Gen eligible |
|----|---------------|---------|------:|------:|-------------------|-----------------|---------|----------|-----------|-------------|--------------|
| `b524db7f…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-1.pdf` | BIOLOGY | 11 | 9 | `62408711fab3…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `65420dde…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-10.pdf` | BIOLOGY | 11 | 11 | `26dcb5a4021c…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `5decdc2c…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf` | BIOLOGY | 11 | 22 | `e2dbdb1ec779…` | DISCOVERED | MAPPED | 16 | 4 | True | True |
| `ca7298fd…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-12.pdf` | BIOLOGY | 11 | 13 | `a6e2c42534a8…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `40924853…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf` | BIOLOGY | 11 | 15 | `39014c593bb6…` | DISCOVERED | UNMAPPED | 4 | 0 | False | False |
| `01eb4c6d…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-14.pdf` | BIOLOGY | 11 | 12 | `a4b1d577517f…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `3a4009db…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-15.pdf` | BIOLOGY | 11 | 12 | `ad30d706c7f9…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `24930268…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-16.pdf` | BIOLOGY | 11 | 12 | `33985e227406…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `6d1d1839…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-17.pdf` | BIOLOGY | 11 | 13 | `d9afb221cc68…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `b6b70f80…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-18.pdf` | BIOLOGY | 11 | 9 | `bfdae5a581e1…` | DISCOVERED | MAPPED | 0 | 0 | True | False |
| `b7d34f93…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-19.pdf` | BIOLOGY | 11 | 14 | `dd3a77420a33…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `20107afe…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-2.pdf` | BIOLOGY | 11 | 13 | `023adc154e4b…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `25f2af3d…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-3.pdf` | BIOLOGY | 11 | 14 | `7fc8d9e8416e…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `758d4489…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf` | BIOLOGY | 11 | 18 | `2c092dd3d16c…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `9110c412…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-5.pdf` | BIOLOGY | 11 | 16 | `2eaa97b21ca5…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `ed9c6143…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-6.pdf` | BIOLOGY | 11 | 8 | `6fc1a4034e49…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `f42c82b0…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-7.pdf` | BIOLOGY | 11 | 6 | `9e5c8d0da46c…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `22210e42…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-8.pdf` | BIOLOGY | 11 | 19 | `aba8c632b490…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `1a7beb5b…` | `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-9.pdf` | BIOLOGY | 11 | 16 | `765d3b377196…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `30d51f68…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-1.pdf` | BIOLOGY | 12 | 25 | `9c77b052df55…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `73832664…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-10.pdf` | BIOLOGY | 12 | 11 | `6a3541201178…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `eeebcf9c…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-13.pdf` | BIOLOGY | 12 | 13 | `c02b00783a53…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `20eed356…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-3.pdf` | BIOLOGY | 12 | 10 | `5ada20f49683…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `50997422…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-4.pdf` | BIOLOGY | 12 | 28 | `f907fc983037…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `0122fb1b…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-5.pdf` | BIOLOGY | 12 | 31 | `de949d428a52…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `0f4c1290…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-6.pdf` | BIOLOGY | 12 | 17 | `7b5556a14b7d…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `20adcc85…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-7.pdf` | BIOLOGY | 12 | 22 | `d84fe669807c…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `f100b5e0…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-8.pdf` | BIOLOGY | 12 | 12 | `0d6e1b7edf95…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `0512be3e…` | `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-9.pdf` | BIOLOGY | 12 | 16 | `f9c042d02fdb…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `1b04881f…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-1.pdf` | CHEMISTRY | 11 | 28 | `6bf950c4390c…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `02ffc112…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-2.pdf` | CHEMISTRY | 11 | 45 | `68fc9ec16cc7…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `29b52931…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-3.pdf` | CHEMISTRY | 11 | 26 | `1bcf97d721b9…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `ab567276…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf` | CHEMISTRY | 11 | 36 | `3c583e5d705b…` | DISCOVERED | MAPPED | 118 | 29 | True | True |
| `0a6b8706…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-5.pdf` | CHEMISTRY | 11 | 32 | `f11159a7fda0…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `e403bb6b…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-6.pdf` | CHEMISTRY | 11 | 47 | `24f9d0236260…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `fa62e975…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-7.pdf` | CHEMISTRY | 11 | 21 | `12b98a00f69b…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `15bbdd1d…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-8.pdf` | CHEMISTRY | 11 | 39 | `6b3e7a38c4f7…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `07112b72…` | `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-9.pdf` | CHEMISTRY | 11 | 33 | `ba399faf5d94…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `23eef141…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-1.pdf` | CHEMISTRY | 12 | 30 | `118c5745258e…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `8240ea96…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-10.pdf` | CHEMISTRY | 12 | 22 | `6a2af1b8eb5d…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `eaa89863…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-2.pdf` | CHEMISTRY | 12 | 30 | `4451b11856a1…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `e62d0342…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-3.pdf` | CHEMISTRY | 12 | 28 | `4bd8d9f62cd5…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `6945a44c…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-4.pdf` | CHEMISTRY | 12 | 29 | `e6c1ffee237f…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `d444fe53…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-5.pdf` | CHEMISTRY | 12 | 23 | `a96fcf6ce050…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `b7e2d3e7…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-6.pdf` | CHEMISTRY | 12 | 34 | `e1c48ac69640…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `ce1bdbf1…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-7.pdf` | CHEMISTRY | 12 | 34 | `7d1ec26a4886…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `fb5632ef…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-8.pdf` | CHEMISTRY | 12 | 32 | `d749b90f53b5…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `1d8fa4dc…` | `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-9.pdf` | CHEMISTRY | 12 | 22 | `a47ce63c870b…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `d65a4f26…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf` | PHYSICS | 11 | 12 | `3efff81bec6f…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `a38110a8…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-11.pdf` | PHYSICS | 11 | 18 | `eab94e616f83…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `8b80163d…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-12.pdf` | PHYSICS | 11 | 15 | `413ea2c7afc7…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `70498c6d…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-13.pdf` | PHYSICS | 11 | 19 | `55abe21cd9ef…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `7ae25d5b…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-14.pdf` | PHYSICS | 11 | 22 | `048d43cc03a3…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `59569c87…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-2.pdf` | PHYSICS | 11 | 14 | `3b6359fd23dd…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `700b11f1…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-3.pdf` | PHYSICS | 11 | 22 | `190e8b0401c5…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `b13faa39…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-4.pdf` | PHYSICS | 11 | 22 | `038112bf72e6…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `e5b84df2…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-5.pdf` | PHYSICS | 11 | 21 | `354d40302e7d…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `48c1b0cf…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-6.pdf` | PHYSICS | 11 | 35 | `fff94dc8268c…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `04610bac…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-8.pdf` | PHYSICS | 11 | 13 | `c63a59bf3392…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `ae9f3f7f…` | `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-9.pdf` | PHYSICS | 11 | 22 | `83f687e060f1…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `7d985176…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-1.pdf` | PHYSICS | 12 | 44 | `98c9fce4f3f5…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `5005f0ee…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-2.pdf` | PHYSICS | 12 | 36 | `84fdc8796e78…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `264c1f82…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf` | PHYSICS | 12 | 26 | `76cd7927ef3c…` | DISCOVERED | MAPPED | 67 | 18 | True | True |
| `fac8ff98…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-4.pdf` | PHYSICS | 12 | 29 | `bdd0d2aa0027…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `6911bd68…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-5.pdf` | PHYSICS | 12 | 18 | `866fae3f3198…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `fe33d785…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-6.pdf` | PHYSICS | 12 | 23 | `80912e330dc1…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `f60932d0…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-7.pdf` | PHYSICS | 12 | 24 | `a76a376dd512…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |
| `61d14596…` | `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-8.pdf` | PHYSICS | 12 | 14 | `dd154366b5cb…` | DISCOVERED | UNMAPPED | 0 | 0 | False | False |

## Verification rules applied

1. NEET scope = `Physics/`, `Chemistry/`, `Biology/` under `StudyMaterial/` only.
2. Subject eligibility verified via directory root + DB `subject_code`, not filename alone.
3. Biology → Botany/Zoology split only where explicit `source_academic_mappings` exist (ADR-0031).
4. **Generation eligible (source-grounded)** = MAPPED + ≥1 ingestion job + ≥1 PASSED KnowledgeUnit.
