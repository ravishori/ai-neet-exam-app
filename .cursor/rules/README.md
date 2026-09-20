# `.cursor/rules` — compact hierarchy

Permanent TALOS agent policy. See also `docs/architecture/cursor_task_protocol.md`.

| File | alwaysApply | Notes |
|------|-------------|--------|
| `project-core.mdc` | yes | Priorities + source honesty |
| `neet-2026-syllabus-boundary.mdc` | yes | **Do not weaken** — dual syllabus/NCERT gates |
| `ncert-source-boundary.mdc` | yes | Canonical `NCERT Books/` factual root |
| `studymaterial-archive.mdc` | yes | Legacy archive path only (not NCERT evidence) |
| `content-safety.mdc` | yes | No generate/publish/provider by default |
| `content-factory.mdc` | scoped | CMS pipeline / constraint merges |
| `mcq-quality.mdc` | scoped | Item quality bar |
| `database-safety.mdc` | yes | Surgical DB + measured counts |
| `audit-protocol.mdc` | yes | Audit cadence + artifact authority |

Task prompts should reference audit JSON populations instead of repeating these rules.
