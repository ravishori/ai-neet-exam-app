# TALOS Volume 1 — Executive & Product Blueprint

This folder holds **Volume 1** of the Trinetra AI Learning OS (TALOS) blueprint
series: the executive and product narrative for the AI NEET Exam App vertical.

## Structure

| Path | Chapters | Contents |
|---|---|---|
| `01-front-matter-and-strategy.md` | 1–12 | Cover, document control, executive summary, vision/mission/strategy |
| `02-market-and-business.md` | 13–18 | Market, industry, competitors, SWOT, business model, stakeholders |
| `03-product-design.md` | 19–23 | Personas, customer journey, problem, solution, value proposition |
| `04-requirements-and-scope.md` | 24–30 | Functional/NFR, business rules, scope, assumptions, constraints |
| `05-risk-metrics-governance.md` | 31–40 | Risks, mitigation, KPIs, success, roadmap, release, governance, appendices, glossary, references |
| `VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md` | 1–40 | **Master DOCX-ready assembly** (~115k words / ~288 pages @ 400 wpp) |
| `VOLUME_01_PDF_FRIENDLY.md` | 1–40 | Same master with `\newpage` markers for pandoc PDF |
| `TALOS-VOL-01-Executive-Product-Blueprint.docx` | 1–40 | Generated Word document (`_md_to_docx.py`) |
| `diagrams/` | — | Mermaid, PlantUML, draw.io assets (see `diagrams/README.md`) |
| `build-docx.md` | — | Assembly and Pandoc notes |
| `_assemble_volume.py` | — | Re-assemble master from parts |
| `_md_to_docx.py` | — | Markdown → DOCX (python-docx) |
| `README.md` | — | This file |

## How to assemble

Concatenate parts in order (Part A already carries Pandoc YAML front matter).
Strip YAML from later parts if present. Insert `\newpage` between parts for
DOCX/PDF pagination.

PowerShell (also documented in `build-docx.md`):

```powershell
$dir = "docs/blueprint/volume-01"
$out = Join-Path $dir "VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md"
$parts = @(
  "01-front-matter-and-strategy.md",
  "02-market-and-business.md",
  "03-product-design.md",
  "04-requirements-and-scope.md",
  "05-risk-metrics-governance.md"
) | ForEach-Object { Join-Path $dir $_ }

Get-Content $parts[0] -Raw | Set-Content $out -Encoding utf8
foreach ($p in $parts[1..($parts.Length-1)]) {
  Add-Content $out "`n\newpage`n"
  Add-Content $out (Get-Content $p -Raw)
}
```

Or re-run the assembler script if present / regenerate the master after editing
any part file.

## Pandoc DOCX command

```bash
pandoc "docs/blueprint/volume-01/VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md" \
  -o "docs/blueprint/volume-01/TALOS-VOL-01-Executive-Product-Blueprint.docx" \
  --from markdown --to docx \
  --toc --toc-depth=3 \
  -V geometry:margin=1in
```

PowerShell:

```powershell
pandoc "docs/blueprint/volume-01/VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md" `
  -o "docs/blueprint/volume-01/TALOS-VOL-01-Executive-Product-Blueprint.docx" `
  --from markdown --to docx --toc --toc-depth=3 -V geometry:margin=1in
```

Notes:

- Mermaid/PlantUML fences may not become images in DOCX unless you add a filter
  or pre-export SVGs/PNGs from `diagrams/`.
- Git Markdown is the source of truth; DOCX is a distribution format.

## Accuracy and conflict notes

**Conflict order (normative):**

1. Running code under `apps/`
2. Accepted ADRs in `docs/decisions/`
3. Deploy docs in `docs/deploy/`
4. This Volume narrative
5. Diagrams

Known honesty constraints:

- CI/CD and Coolify paths are documented (`ADR-0029`, `docs/deploy/*`) but may
  not have been executed against a live GitHub remote yet — treat first use as
  a dry run.
- `KnowledgeUnit` / EKU is canonical (`ADR-0024`–`0028`); embeddings/RAG are
  **FUTURE**; Tutor fully powered by KUs is a disclosed gap in `ADR-0028`.
- `BRD.docx` is vision/backlog, not the build spec; `ADR-0007` cuts remain binding.
- Naming: always **Trinetra AI Learning OS (TALOS)** (`ADR-0010`).
- Commerce is one-time Razorpay; subscriptions are **FUTURE**.
- Multi-exam packaging, full KG, 12-agent OS, digital twin, multi-tenant portals
  are deferred / FUTURE — never implied as Volume 1 delivery.

## Companion volumes (planned)

| Volume | Intent |
|---|---|
| Volume 2 — Engineering deep dive | Module APIs, schema catalog, test matrices |
| Volume 3 — Content operations handbook | ECAEP SOPs, licensing intake, ingestion |
| Volume 4 — AI systems workbook | Gateway, prompts, cost, evaluation |
| Volume 5 — Launch & GTM | Pricing/cohort playbooks (must not break freezes) |

Companions deepen Volume 1; they must not contradict architecture freeze,
licensing, or deploy topology without a new ADR.

## Diagram index

See [`diagrams/README.md`](diagrams/README.md).
