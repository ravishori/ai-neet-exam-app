# SOURCE INGESTION COMPLETION REPORT — FACTORY-S1

**Generated:** 2026-09-01T18:00:34.504813+00:00  
**Mode:** LIVE source ingestion (no AI, no MCQ)  
**Run ID:** `factory-s1-source-ingestion-v1`

## Summary

| Metric | Before | After | Δ |
|--------|-------:|------:|--:|
| Registered NEET sources | 68 | 68 | +0 |
| Sources with completed ingestion | 4 | 68 | +64 |
| Ingestion sections | 232 | 1435 | +1203 |
| Knowledge Units (total) | 69 | 73 | +4 |
| KU PASSED | 58 | 62 | +4 |
| KU FAILED | 11 | 11 | +0 |
| Chapters with full source→KU coverage | 3 | 4 | +1 |

- Discovery newly registered: **0**
- Academic mappings synced: **4** / 68 mapped
- Duplicate/prior jobs skipped: **66**
- Per-source errors: **0**

## Mathematics exclusion

- Maths rows in `source_documents`: **0** (expected 0)
- Maths filesystem directories are ignored at discovery — never deleted or modified.

## Failed Knowledge Unit classification

| Category | Count |
|----------|------:|
| duplicate | 10 |
| validation | 1 |

- `28c8ed0d…` **PHYSICS/current-electricity/kcl-kvl** — duplicate: duplicate of existing knowledge unit 21dbedd9-3c41-45be-8fe2-4fc0df9e5bfc
- `214fb8ae…` **PHYSICS/current-electricity/ohms-law-concept** — duplicate: duplicate of existing knowledge unit da6373e3-0038-4ed2-aa6e-c33e583d4874
- `bcb1d610…` **PHYSICS/current-electricity/ohms-law-concept** — duplicate: duplicate of existing knowledge unit b1b0eb35-134c-46ac-9cbb-e217d05c4313
- `35b17f84…` **PHYSICS/current-electricity/kcl-kvl** — duplicate: duplicate of existing knowledge unit e859b94c-6b96-4974-bfab-c4fceaeb8688
- `9757105c…` **PHYSICS/current-electricity/kcl-kvl** — duplicate: duplicate of existing knowledge unit 21dbedd9-3c41-45be-8fe2-4fc0df9e5bfc
- `f73425b2…` **PHYSICS/current-electricity/ohms-law-concept** — duplicate: duplicate of existing knowledge unit da6373e3-0038-4ed2-aa6e-c33e583d4874
- `0b5bc48e…` **PHYSICS/current-electricity/ohms-law-concept** — duplicate: duplicate of existing knowledge unit b1b0eb35-134c-46ac-9cbb-e217d05c4313
- `bfd8bb88…` **PHYSICS/current-electricity/factors-affecting-resistance** — duplicate: duplicate of existing knowledge unit 1897bbf3-23c4-4518-97bd-feefec5c8656
- `613e6d0d…` **PHYSICS/current-electricity/factors-affecting-resistance** — duplicate: duplicate of existing knowledge unit 6ffaf183-d92c-4bb5-8a3b-60de89585465
- `0b0c231c…` **PHYSICS/current-electricity/kcl-kvl** — duplicate: duplicate of existing knowledge unit e859b94c-6b96-4974-bfab-c4fceaeb8688
- `ba4200b6…` **CHEMISTRY/chemical-bonding/sp-sp2-sp3** — validation: 2/4 facts failed source-overlap check: C2H2 (acetylene) contains both sigma and pi bonds in its structure.; C2H4 (ethyle

## Per-source results

Total processed: 68 · Skipped (idempotent): 66 · Failed: 0

- OK `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-1.pdf` — sections=10, KU +0/−0
- OK `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-10.pdf` — sections=12, KU +0/−0
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf` (existing job f5b496d3-399c-4290-8fc2-e9deac412a71)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-12.pdf` (existing job d14ec4e6-917b-4143-9657-4ee6a6b8c2cf)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf` (existing job 159c82e6-f35d-4aed-bbb9-4697f5abea60)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-14.pdf` (existing job a7d28f40-f5e3-4192-8b34-33b22a2a3ffa)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-15.pdf` (existing job b7bcc2e1-98c0-491c-956b-61bd386ed1c5)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-16.pdf` (existing job ed449c49-e359-4609-88df-17806d31cc1e)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-17.pdf` (existing job 5f418996-947d-4c33-99f9-b46770f44991)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-18.pdf` (existing job 985e13aa-b686-4563-8846-d3ff7e834156)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-19.pdf` (existing job d2f8f532-beb0-41e5-92b8-102f4cfea2ba)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-2.pdf` (existing job 9a3f8bd8-b7c4-408f-a609-e75f14e9dfd0)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-3.pdf` (existing job 1f488f7b-2223-4f0c-963e-c4f5254962f0)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf` (existing job 48fded77-9a8c-4b35-8bc4-645ef47abe36)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-5.pdf` (existing job d2180783-4bdb-47ce-8737-32cbf0b4896b)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-6.pdf` (existing job e10c88da-b38e-448f-8430-72235a45cb29)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-7.pdf` (existing job db6aabcf-72ec-4a39-996d-1e10c1497282)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-8.pdf` (existing job cc4d7bef-2877-4e06-98dd-20f42391b299)
- SKIP `Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-9.pdf` (existing job 194722fe-76ab-4cdc-86a5-b00ebf6c94e9)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-1.pdf` (existing job 5552df65-6ee7-4b6c-8db5-20ef117cd6ee)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-10.pdf` (existing job 3c9f2ac0-8e35-438f-8738-cd580a89a7f5)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-13.pdf` (existing job 7e7d603f-f15e-42c1-bd83-a8af8c89155b)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-3.pdf` (existing job 387447ed-0532-4ce7-8d05-977ec6b327f2)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-4.pdf` (existing job a1ce413f-7446-445c-a7d4-d8ef2266f8b6)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-5.pdf` (existing job 07f3dca5-c33e-4c3d-872f-87dfaef15f72)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-6.pdf` (existing job ae79f6e4-2ddd-41ba-abd7-515deb18d927)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-7.pdf` (existing job 15121dcf-e487-4037-8e26-362db0ce7d09)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-8.pdf` (existing job e22294df-d947-4758-8eca-0e2097c95d34)
- SKIP `Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-9.pdf` (existing job a10d003c-0ee2-4ad2-b00c-4e9b1be632c3)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-1.pdf` (existing job c4aa0cb8-6032-4434-8199-af698f5176d9)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-2.pdf` (existing job ff64469d-af0b-4098-be3c-601c19f0575f)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-3.pdf` (existing job 54b33b5b-4ae8-4a25-b7b2-d9da9b6b69aa)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf` (existing job da6a1664-e169-4e4d-873b-898e5f8c69ed)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-5.pdf` (existing job 89b15ed0-0b27-4845-9b3c-5a4d07bfc354)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-6.pdf` (existing job 4ecf7ab8-3640-447d-bd38-834c6747a15a)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-7.pdf` (existing job 380fd8f7-90c2-4acc-8a1b-4db64fb9357a)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-8.pdf` (existing job 4c04be24-7fb2-4fd5-8974-7cafbeb52202)
- SKIP `Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-9.pdf` (existing job 8eb31cb0-5231-441f-82bf-c889073d2f90)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-1.pdf` (existing job 1cf3d17e-14af-4ae4-aa31-caf7759afa3c)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-10.pdf` (existing job 86e00cab-48ca-485d-8953-aef9c56ad5d1)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-2.pdf` (existing job 9048c3d9-3cc9-455f-a65f-43e2c74ac772)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-3.pdf` (existing job 8c540d73-8b94-4488-9121-5658ef8715a0)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-4.pdf` (existing job 917f4267-3c8a-4c7c-9b2b-889de300353b)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-5.pdf` (existing job e89f7cf6-c2c1-4e2d-aa71-9d2d619d92ad)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-6.pdf` (existing job b4357737-4fde-4cf3-86a9-68a8bdc74b04)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-7.pdf` (existing job 5903dc93-956b-45c4-9ced-50086a31b296)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-8.pdf` (existing job 29d5a582-b456-4533-8c44-27f895ea8f94)
- SKIP `Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-9.pdf` (existing job 8c9025cd-d94f-4955-b7c4-690d1bf84f62)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf` (existing job 566ffd46-0bd5-46e1-9553-020051fcec2d)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-11.pdf` (existing job 424b3363-8a6e-4bcc-9609-63aae4cfa01e)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-12.pdf` (existing job 1065a1fb-eb3b-4a81-830b-4cc7e54b5a0e)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-13.pdf` (existing job 1d1094c2-44b9-4cd8-9b72-3967a87d18c2)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-14.pdf` (existing job f1bd1a03-f615-48d8-8b62-81acd3e6c987)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-2.pdf` (existing job 179309fe-1294-4b94-9ad1-569da0453e11)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-3.pdf` (existing job 937411bd-f630-42ef-9ae6-bda0babc1ea7)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-4.pdf` (existing job 74c122c3-3f85-47b5-80af-409ea36ce344)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-5.pdf` (existing job bf482e1e-a555-4c32-8785-abb51b3dbc6f)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-6.pdf` (existing job c4151176-a011-4a2c-b56e-30529024d2fc)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-8.pdf` (existing job 54426785-5fb1-4de8-845a-d33bf1d5b1ba)
- SKIP `Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-9.pdf` (existing job 3eaf3ade-5c3d-43ce-8341-42ca6ffbbd7b)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-1.pdf` (existing job bb322ec7-0fa9-4841-969a-483951b0d47f)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-2.pdf` (existing job 21d318e7-bd08-4640-8927-d496a205bba1)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf` (existing job a60ef885-2b4e-42ed-bb51-00627ede5747)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-4.pdf` (existing job f5e98334-3ca9-43d5-a824-cca2dd0453e8)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-5.pdf` (existing job 88118f04-ba06-4f57-832d-3c813ce18284)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-6.pdf` (existing job e12d2df6-b39b-402b-925d-b1f925879a73)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-7.pdf` (existing job 5571b59c-56d0-425d-b2ed-9ca0894fe934)
- SKIP `Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-8.pdf` (existing job 47347899-bf4c-42ba-8f14-a22a1c91d924)

## Database integrity

- No MCQ generation executed
- No ECAEP / publish / P4 / P5
- Source checksums preserved (verified on job start)
- Idempotent re-run skips completed S1 or prior completed ingestion jobs

## Tests

Run: `pytest app/modules/ingestion/tests/test_source_ingestion_s1.py app/modules/ingestion/tests/test_study_material_discovery.py -q`
