"""MCQ-FACTORY-GROQ-001 — source-grounded NEW QUESTION GENERATION pipeline.

This package builds ORIGINAL NEET-UG practice-question candidates grounded
in local NCERT/StudyMaterial PDFs, for the Groq openai/gpt-oss-20b
(generation) / openai/gpt-oss-120b (verification) models. Nothing in this
package calls a live AI API or writes to a non-local database — see each
module's docstring. The bulk-run CLI
(scripts/mcq_factory_groq_bulk_run.py) is the only intended live-call
entrypoint, and it requires an explicit, off-by-default operator opt-in.
"""

from __future__ import annotations
