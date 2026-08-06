# Volume 1 — Diagram assets

Companion visuals for **Trinetra AI Learning OS (TALOS)** Volume 1.
Narrative lives in `../VOLUME_01_EXECUTIVE_PRODUCT_BLUEPRINT.md` and part files.

## Index

| File | Format | Topic | Used in |
|---|---|---|---|
| `capability-map.mmd` | Mermaid | Platform capability map | Ch. 8–12, App. J |
| `c4-context.mmd` | Mermaid (C4) | System context | Architecture chapters |
| `c4-container.mmd` | Mermaid (C4) | Web, API, PG, Redis, externals | Architecture chapters |
| `ecaep-state.mmd` | Mermaid | ECAEP workflow states | Content / App. E |
| `student-journey.mmd` | Mermaid | Learner end-to-end journey | Ch. 20 |
| `learning-loop.mmd` | Mermaid | Practice → mastery → recommend | Learning chapters |
| `module-dependencies.puml` | PlantUML | Backend module dependencies | Architecture / App. C |
| `release-flow.puml` | PlantUML | CI → GHCR → Coolify → verify/rollback | Ch. 36 |
| `stakeholder-map.puml` | PlantUML | Stakeholder map | Ch. 18 / Ch. 37 |
| `org-capability-map.drawio` | draw.io XML | Org × capability RACI overlay | App. J |

## Rendering

```bash
# Mermaid CLI (optional)
mmdc -i capability-map.mmd -o capability-map.svg

# PlantUML
plantuml module-dependencies.puml
plantuml release-flow.puml
plantuml stakeholder-map.puml
```

Open `org-capability-map.drawio` in [diagrams.net](https://app.diagrams.net/)
or a Draw.io IDE extension.

## Accuracy

- Module names match `apps/backend/app/modules/*` through ADR-0029.
- ECAEP states match `docs/architecture/ecaep.md` / ADR-0009.
- Deploy path matches `docs/deploy/CI_CD.md`, `RUNBOOK.md`, `ROLLBACK.md`, ADR-0029
  (Coolify builds from git; GHCR is for traceability).
- FUTURE capabilities appear only when labeled FUTURE.

**Conflict rule:** code + Accepted ADR win over diagrams.
