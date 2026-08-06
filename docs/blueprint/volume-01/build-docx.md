# Building DOCX / PDF-friendly outputs for Volume 1

## Prerequisites

- [Pandoc](https://pandoc.org/) 3.x+
- Optional: a Word reference doc for fonts/styles
- Optional PDF engine: `wkhtmltopdf`, WeasyPrint, or LaTeX

## Assemble master (PowerShell)

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

# Strip duplicate YAML from parts 2+ when concatenating if needed.
Get-Content $parts[0] | Set-Content $out -Encoding UTF8
foreach ($p in $parts[1..($parts.Length-1)]) {
  Add-Content $out "`n\newpage`n"
  Get-Content $p | Add-Content $out
}
```

## DOCX

```bash
pandoc docs/blueprint/volume-01/VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md \
  -o docs/blueprint/volume-01/TALOS-VOL-01-Executive-Product-Blueprint.docx \
  --from markdown --to docx \
  --toc --toc-depth=3 \
  -V geometry:margin=1in
```

Mermaid/PlantUML diagrams render as code blocks in DOCX unless you pre-render them to images and link those images. For publication, export diagrams from `diagrams/` to PNG/SVG and replace fenced blocks as needed.

## PDF-friendly Markdown

The master Markdown is PDF-friendly when processed with pandoc:

```bash
pandoc docs/blueprint/volume-01/VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md \
  -o docs/blueprint/volume-01/TALOS-VOL-01-Executive-Product-Blueprint.pdf \
  --toc --toc-depth=3 \
  -V documentclass=report \
  -V papersize=a4
```

## Quality checklist before distribution

- [ ] Conflict Register present and accurate
- [ ] No claim that OpenAI/Azure/RAG/CQRS/KG are shipped
- [ ] SP0–SP9 marked done per roadmap
- [ ] Enterprise Assumptions labeled
- [ ] Glossary and References included
- [ ] Diagrams folder referenced
