#!/usr/bin/env python
"""MCQ-FACTORY-GROQ-001 — bulk-run CLI for the Groq-/OpenRouter-backed NEW
QUESTION GENERATION pipeline.

SAFETY CONTRACT (read before touching this file):

  1. This script NEVER makes a live network call by default. ``--dry-run``
     defaults to True.
  2. Even with ``--no-dry-run``, a live run additionally requires the
     explicit ``--i-understand-this-calls-a-live-paid-api`` flag, which
     defaults to False and is NOT set by any other code path, env var, or
     config file in this repository.
  3. The live path (``run_live`` below) is a THIN invocation layer over the
     already-tested ``app.modules.cms.mcq_factory_groq.orchestrator.
     GroqFactoryOrchestrator`` — it builds FactSpecs from ``--fact-pack``,
     indexes ``--evidence-pdf`` once, constructs the real generation/
     verification callers via the PROVIDER-AGNOSTIC
     ``orchestrator.build_mcq_factory_generation_caller``/
     ``build_mcq_factory_verification_caller`` (NEET-MCQ-FACTORY-OPENROUTER-
     PRODUCTIONIZED-20261013 — these resolve the real provider+model via
     ``mcq_llm_provider.resolve_mcq_factory_stage_selection``, defaulting to
     Groq when ``MCQ_FACTORY_GENERATION_PROVIDER``/``_VERIFICATION_PROVIDER``
     are unset, so Groq's own behavior is unchanged; setting either to
     ``openrouter`` drives this CLI against OpenRouter instead, which this
     script previously could not do without a one-off throwaway script),
     and calls ``orchestrator.run_batch``. It never re-implements budget/
     rate/retry/validation/publication-gate logic itself.
  4. ``--dry-run`` (the default) performs ZERO imports of any HTTP client
     and constructs ZERO provider instances — see ``print_plan()``, which
     only reads ``GroqFactoryLimits`` (pure settings, no network) and, if
     ``--fact-pack``/``--evidence-pdf`` were passed, only checks whether the
     paths exist on disk (no file content is read, no PDF is parsed).
  5. The live path FAILS CLOSED before constructing anything real: missing
     ``GROQ_API_KEY``/``OPENROUTER_API_KEY``, ``GROQ_ENABLED=false``/
     ``OPENROUTER_ENABLED=false``, a generation-provider selection that does
     not resolve to one of ``_SUPPORTED_LIVE_GENERATION_PROVIDERS``
     (``groq``, ``openrouter``), or a missing/malformed
     ``--fact-pack``/``--evidence-pdf`` all refuse to run with a clear
     error (exit code 4) rather than silently continuing in some degraded
     mode. See ``_check_required_live_config`` / ``_load_fact_specs``.
  6. The ONLY database write path reachable from this CLI is
     ``app.modules.cms.services.generation_staging_store.insert_staging_candidate``
     (the approved non-production staging table), wrapped by
     ``default_live_dependencies``'s ``staging_writer`` closure. That
     function asserts the configured database resolves to localhost/
     127.0.0.1 (``assert_local_database_target``) BEFORE any session is
     ever used. Nothing in this CLI path can reach ``cms.content_items`` or
     any other production table, and nothing auto-publishes a question —
     every candidate lands in ``generation_staging.candidates`` with
     outcome ACCEPTED/REVIEW_REQUIRED/REJECTED, for a human review workflow
     to pick up later.

Usage:
  python scripts/mcq_factory_groq_bulk_run.py --batch-id demo-001 --count 10
      (dry run — prints the plan only, confirmed no network calls)

  python scripts/mcq_factory_groq_bulk_run.py --batch-id demo-001 \\
      --fact-pack data/fact_packs/demo.json --evidence-pdf data/ncert/ch1.pdf \\
      --no-dry-run --i-understand-this-calls-a-live-paid-api
      (a REAL live run — only proceeds if GROQ_API_KEY/GROQ_ENABLED/the
       generation-provider selection are all valid; see the safety contract
       above. This task built and tested this wiring with mocks ONLY — it
       was never executed against the live Groq API.)

``--fact-pack`` is a JSON file holding a non-empty array of fact objects,
each shaped like::

    {
      "fact_id": "phy11-u1-f001",
      "subject": "PHYSICS",
      "unit_number": 1,
      "chapter": "Laws of Motion",
      "topic": "force and acceleration",
      "class_level": "11",
      "taxonomy": {"subject_id": "...", "chapter_id": "...", "topic_id": "...", "concept_id": null},
      "concept": null,
      "unit_name": null,
      "academic_subject_code": null,
      "calculation_check": null
    }

See ``app.modules.cms.mcq_factory_groq.orchestrator.FactSpec`` for the
authoritative field list. ``--evidence-pdf`` is ONE local PDF shared by
every fact in the pack (matching ``GroqFactoryOrchestrator.run_batch``'s
one-document-per-batch shape); it is indexed once via
``pdf_text_index.index_pdf``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable

# Make `app.*` importable when run as `python scripts/mcq_factory_groq_bulk_run.py`
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


class CliConfigError(RuntimeError):
    """Raised to fail CLOSED on missing/invalid required configuration or
    inputs for a live run. Always surfaces a clear, specific message and a
    non-zero exit code — never caught silently, never leads to a degraded
    default behaviour that could mask a misconfiguration."""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-id", required=True, help="Identifier for this generation batch.")
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Cap on the number of facts processed from --fact-pack (plan-display only in dry-run).",
    )
    parser.add_argument(
        "--fact-pack",
        dest="fact_pack",
        type=Path,
        default=None,
        help=(
            "JSON file: a non-empty array of fact objects (see module docstring / "
            "orchestrator.FactSpec). REQUIRED for a live run; ignored (not read) in dry-run "
            "beyond an existence check."
        ),
    )
    parser.add_argument(
        "--evidence-pdf",
        dest="evidence_pdf",
        type=Path,
        default=None,
        help=(
            "Local PDF indexed once and shared by every fact in --fact-pack. REQUIRED for a "
            "live run; ignored (not read) in dry-run beyond an existence check."
        ),
    )
    parser.add_argument(
        "--checkpoint-path",
        type=Path,
        default=Path("data/generated_mcqs/mcq_factory_groq_checkpoint.json"),
        help="Resumable checkpoint file (see mcq_factory_groq_controls.GroqFactoryCheckpoint).",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Print the execution plan only. No network calls. This is the default.",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Attempt a real run. Also requires --i-understand-this-calls-a-live-paid-api.",
    )
    parser.add_argument(
        "--i-understand-this-calls-a-live-paid-api",
        dest="live_opt_in",
        action="store_true",
        default=False,
        help=(
            "Required, explicit opt-in before ANY live Groq call could ever be attempted. "
            "Defaults to False. Never set automatically by this repo."
        ),
    )
    parser.add_argument(
        "--max-attempts-per-fact",
        dest="max_attempts_per_fact",
        type=int,
        default=1,
        help=(
            "NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: how many generation attempts to try per "
            "fact (default 1 — full backward compatibility, byte-identical to before this "
            "flag existed). Each extra attempt uses a different deterministic question-angle "
            "(see prompt_templates.angle_for_attempt) and is skipped automatically once an "
            "earlier attempt on the same fact came back REJECTED (see "
            "GroqFactoryOrchestrator.run_batch's sequencing policy)."
        ),
    )
    parser.add_argument(
        "--budget-profile",
        dest="budget_profile",
        choices=["pilot", "general"],
        default="pilot",
        help=(
            "Which GroqFactoryLimits spend ceiling to use. 'pilot' (the default) uses "
            "GroqFactoryLimits.pilot_profile() — settings.mcq_factory_groq_pilot_max_spend_usd "
            "($5 by default), the dedicated ceiling for the human-authorized 100-question "
            "pilot. 'general' uses GroqFactoryLimits.from_settings() — the broader, separately "
            "configurable settings.mcq_factory_groq_max_spend_usd ($20 by default)."
        ),
    )
    return parser


def print_plan(args: argparse.Namespace, limits) -> None:  # limits: GroqFactoryLimits
    print("MCQ Factory (Groq) — execution plan (DRY RUN, no network calls, no provider constructed)")
    print(f"  batch_id:              {args.batch_id}")
    print(f"  requested count cap:   {args.count if args.count is not None else '(no cap — full fact pack)'}")
    print(f"  fact pack path:        {args.fact_pack} (exists={args.fact_pack.exists() if args.fact_pack else 'N/A'})")
    print(
        "  evidence pdf path:     "
        f"{args.evidence_pdf} (exists={args.evidence_pdf.exists() if args.evidence_pdf else 'N/A'})"
    )
    print(f"  checkpoint path:       {args.checkpoint_path}")
    print(f"  max attempts/fact:     {args.max_attempts_per_fact}")
    print(f"  budget profile:        {args.budget_profile}")
    print(f"  spend ceiling (USD):   {limits.max_total_spend_usd}")
    print(
        "  per-question token caps: "
        f"generation={limits.max_generation_tokens_per_question} "
        f"verification={limits.max_verification_tokens_per_question}"
    )
    print(f"  retry budget per call: {limits.max_retries_per_call}")
    print(
        "  rate limit:            "
        f"{limits.rate_limit_requests_per_minute} req/min, "
        f"{limits.rate_limit_tokens_per_minute} tokens/min"
    )
    print(f"  live_opt_in flag set:  {args.live_opt_in}")
    print("No Groq client was constructed. No HTTP request was made. No API key was read.")


# ---------------------------------------------------------------------------
# Fail-closed fact-pack loading (local filesystem + JSON parsing only)
# ---------------------------------------------------------------------------


def _load_fact_specs(path: Path):
    """Load ``--fact-pack`` into a list of ``FactSpec``. Raises
    ``CliConfigError`` (never a bare exception, never a silent empty list)
    on any missing file, invalid JSON, or schema problem — this is the
    fail-closed contract for malformed configuration/input."""
    from pydantic import ValidationError

    from app.modules.cms.mcq_factory_groq.orchestrator import FactSpec
    from app.modules.cms.mcq_factory_groq.schemas import TaxonomyIds
    from app.modules.cms.mcq_factory_groq.syllabus_topic_mapping import (
        resolve_syllabus_topic_id,
    )

    if not path.exists():
        raise CliConfigError(f"--fact-pack path does not exist: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliConfigError(f"--fact-pack is not readable/valid JSON ({path}): {exc}") from exc
    if not isinstance(raw, list) or not raw:
        raise CliConfigError(f"--fact-pack must be a non-empty JSON array of fact objects ({path})")

    specs: list[FactSpec] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise CliConfigError(f"--fact-pack entry {i} is not a JSON object")
        taxonomy_raw = row.get("taxonomy")
        if not isinstance(taxonomy_raw, dict):
            raise CliConfigError(
                f"--fact-pack entry {i} (fact_id={row.get('fact_id')!r}) is missing a 'taxonomy' object"
            )
        try:
            taxonomy = TaxonomyIds(**taxonomy_raw)
            fact_id = str(row["fact_id"])
            # Explicit per-row "syllabus_topic_id" in the fact-pack JSON (if
            # ever added) wins; otherwise fall back to the reviewed
            # fact_id -> syllabus-registry-topic_id lookup table built for
            # NEET-MCQ-FACTORY-TOPIC-MAPPING-FIX-20261012. A fact_id with no
            # entry in either resolves to None, which is correct — the
            # syllabus gate then falls back to the (unchanged) free-text
            # topic exact-match path and blocks it exactly as before. No
            # fuzzy matching is ever applied here.
            syllabus_topic_id = row.get("syllabus_topic_id") or resolve_syllabus_topic_id(fact_id)
            spec = FactSpec(
                fact_id=fact_id,
                subject=str(row["subject"]),
                unit_number=int(row["unit_number"]),
                chapter=str(row["chapter"]),
                topic=str(row["topic"]),
                class_level=str(row["class_level"]),
                taxonomy=taxonomy,
                concept=row.get("concept"),
                unit_name=row.get("unit_name"),
                academic_subject_code=row.get("academic_subject_code"),
                calculation_check=row.get("calculation_check"),
                syllabus_topic_id=syllabus_topic_id,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise CliConfigError(f"--fact-pack entry {i} is invalid: {type(exc).__name__}: {exc}") from exc
        specs.append(spec)
    return specs


# ---------------------------------------------------------------------------
# Fail-closed required-configuration check for a live run
# ---------------------------------------------------------------------------


# Providers this CLI is willing to drive live, via the provider-agnostic
# mcq_factory_<stage>_provider/_model selection (see
# mcq_llm_provider.resolve_mcq_factory_stage_selection). Groq remains the
# default (selected when MCQ_FACTORY_GENERATION_PROVIDER is unset) — adding
# "openrouter" here is the NEET-MCQ-FACTORY-OPENROUTER-PRODUCTIONIZED-20261013
# change that lets this CLI drive OpenRouter live, instead of only a one-off
# throwaway script. "krutrim" (MCQ-FACTORY-KRUTRIM-001) and "deepseek"
# (MCQ-FACTORY-DEEPSEEK-001) are parallel, one-entry additions mirroring
# that same change — not a restructure. "openai" (MCQ-FACTORY-OPENAI-001) is
# the same one-entry addition; the OpenAI provider itself (config fields,
# registry entry, pricing) already existed project-wide before this change,
# this only lets THIS CLI drive it live. Any other resolved provider name
# still fails closed.
_SUPPORTED_LIVE_GENERATION_PROVIDERS = ("groq", "openrouter", "krutrim", "deepseek", "openai")


def _check_required_live_config(settings: Any) -> None:
    """Raise ``CliConfigError`` if required generation-provider
    configuration for a live run is missing or invalid. Never reads,
    prints, or logs any actual API key value — only checks non-emptiness
    after stripping whitespace. Never silently falls back to a different
    provider: the generation-provider selection (via
    ``mcq_llm_provider.resolve_mcq_factory_stage_selection`` — the SAME
    resolution ``default_live_dependencies``'s
    ``build_mcq_factory_generation_caller`` actually uses to construct the
    real caller, so this check can never drift from what the live run
    would really do) must resolve to one of
    ``_SUPPORTED_LIVE_GENERATION_PROVIDERS``, or this CLI refuses.

    NEET-MCQ-FACTORY-OPENROUTER-PRODUCTIONIZED-20261013: this previously
    checked the OLDER, generic ``resolve_mcq_provider_selection``
    (``MCQ_PROVIDER``/``FACTORY_PROVIDER``-driven) and hard-required
    exactly ``'groq'`` — a DIFFERENT settings knob than the one
    ``build_groq_generation_caller``/``build_mcq_factory_generation_caller``
    actually resolve the live provider from. Switching this check to the
    same ``mcq_factory_generation_provider`` knob the live caller itself
    uses is what makes this CLI's OpenRouter support real (previously the
    CLI's declared safety contract and its actual construction path used
    two unrelated settings fields). Groq's own default behavior is
    unaffected: ``mcq_factory_generation_provider`` left unset still
    resolves to ``'groq'`` exactly as before.
    """
    from app.modules.cms.services.mcq_llm_provider import resolve_mcq_factory_stage_selection

    try:
        selection = resolve_mcq_factory_stage_selection("generation", settings=settings)
    except Exception as exc:  # noqa: BLE001 — any resolution failure must fail closed, never be swallowed
        raise CliConfigError(f"MCQ factory generation-provider selection is invalid: {exc}") from exc

    if selection.registry_name not in _SUPPORTED_LIVE_GENERATION_PROVIDERS:
        raise CliConfigError(
            f"MCQ factory generation provider resolves to '{selection.registry_name}' (via "
            "MCQ_FACTORY_GENERATION_PROVIDER), which this CLI does not support for a live run "
            f"(supported: {', '.join(_SUPPORTED_LIVE_GENERATION_PROVIDERS)}). Refusing rather "
            "than silently generating against an unsupported provider."
        )
    env_prefix = selection.registry_name.upper()
    if not selection.enabled:
        raise CliConfigError(
            f"{env_prefix}_ENABLED is False (or unset) — refusing to run live. An operator "
            f"must explicitly set {env_prefix}_ENABLED=true before any live run."
        )
    if not selection.configured:
        detail = f"{env_prefix}_API_KEY is empty/unset"
        if selection.registry_name == "openrouter":
            detail += " and/or OPENROUTER_MODEL is empty/placeholder"
        elif selection.registry_name == "krutrim":
            detail += " and/or KRUTRIM_MODEL is empty/placeholder"
        elif selection.registry_name == "deepseek":
            detail += " and/or DEEPSEEK_MODEL is empty/placeholder"
        raise CliConfigError(
            f"{detail} — refusing to run live. Configure real credentials via the "
            "environment/.env (never pass secrets on the command line)."
        )


# ---------------------------------------------------------------------------
# Live dependency wiring — the ONE place a real AsyncSession, real
# generation/verification callers, and the real (staging-only) write path
# are constructed. Tests inject a fake ``dependencies_factory`` instead of
# ever calling this.
# ---------------------------------------------------------------------------


@dataclass
class LiveDependencies:
    session: Any
    generation_caller: Any
    verification_caller: Any
    taxonomy_resolver: Any
    staging_writer: Callable[[Any], Awaitable[bool]]
    publication_gate_session: Any
    # NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: real cross-BATCH duplicate
    # lookup, reading generation_staging.candidates directly on every
    # call (never a stale snapshot) — see
    # generation_staging_store.find_staging_candidates_by_stem_hash. This
    # is the concrete fix for the "existing_corpus is never populated by
    # this CLI" structural gap (plan §1.3): THIS field is what actually
    # wires real duplicate detection into the live CLI path. Defaults to
    # None (the orchestrator's own default — "skip this check") so any
    # existing fake ``dependencies_factory`` built by a test (which never
    # set this field before this task) keeps working unmodified.
    cross_batch_duplicate_lookup: Callable[[str], Awaitable[list[Any]]] | None = None


DependenciesFactory = Callable[[Any], "AsyncIterator[LiveDependencies]"]


@asynccontextmanager
async def default_live_dependencies(settings: Any) -> AsyncIterator[LiveDependencies]:
    """Production wiring. Reused components ONLY — never reimplemented:

    - ``app.core.database.AsyncSessionLocal`` / ``engine`` — the project's
      single configured engine/session factory (same as every other
      staging-writing script, e.g. ``scripts/generation_staging_pilot_run.py``).
    - ``generation_staging_store.assert_local_database_target`` — called
      BEFORE any session is ever used, exactly like that same existing
      script, so this path can never target a non-local (and therefore
      never a production) database.
    - ``orchestrator.build_mcq_factory_generation_caller`` /
      ``build_mcq_factory_verification_caller`` — the PROVIDER-AGNOSTIC
      adapters (MCQ-FACTORY-PROVIDER-AGNOSTIC-001) that resolve the real
      generation/verification provider+model independently via
      ``mcq_llm_provider.resolve_mcq_factory_stage_selection`` (defaulting
      to Groq when unset — see that function's docstring). This CLI used
      to call the Groq-ONLY ``build_groq_generation_caller`` /
      ``build_groq_verification_caller`` here; NEET-MCQ-FACTORY-OPENROUTER-
      PRODUCTIONIZED-20261013 switched it to the provider-agnostic pair so
      the REAL CLI (not a one-off throwaway script) can drive OpenRouter
      (or any other MCQ_SUPPORTED_PROVIDERS entry) live, the same way the
      real $0-cost OpenRouter test run already proved works — Groq's own
      behavior is unchanged because both adapters resolve to the identical
      Groq provider/model construction when the provider-agnostic
      settings are left unset (see
      ``mcq_llm_provider.build_mcq_factory_stage_provider``'s ``groq``
      branch, which reuses the same ``construct_groq_provider_for_model``
      helper the old Groq-only path relied on).
    - ``validators.build_taxonomy_resolver_from_session`` — the existing
      real-row taxonomy resolver.
    - ``generation_staging_store.insert_staging_candidate`` — the ONLY
      write this module ever issues; never any other table, never an
      auto-publish path.
    - ``generation_staging_store.find_staging_candidates_by_stem_hash`` —
      NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: a REAL, read-only, cross-batch
      duplicate lookup wired into the orchestrator as
      ``cross_batch_duplicate_lookup`` (adapted to
      ``orchestrator.CrossBatchDuplicateMatch``) — this is the concrete
      fix for the gap documented in
      docs/quality/neet_mcq_factory_MULTI_ATTEMPT_PLAN_20261013.md §1.3:
      this function previously never passed ``existing_corpus`` to the
      orchestrator at all, so cross-corpus duplicate detection was a
      structural no-op in every real live run. Groq's/any provider's
      SINGLE-attempt behavior is unaffected except for this new, strictly
      additive check (a candidate whose exact normalized stem already
      exists anywhere in generation_staging.candidates is now correctly
      routed to REVIEW_REQUIRED instead of silently accepted as a second
      copy — a bug fix, not a regression).
    """
    from app.core.database import AsyncSessionLocal, engine
    from app.modules.cms.mcq_factory_groq.orchestrator import (
        CrossBatchDuplicateMatch,
        build_mcq_factory_generation_caller,
        build_mcq_factory_verification_caller,
    )
    from app.modules.cms.mcq_factory_groq.validators import build_taxonomy_resolver_from_session
    from app.modules.cms.services.generation_staging_store import (
        assert_local_database_target,
        find_staging_candidates_by_stem_hash,
        insert_staging_candidate,
    )

    # Belt-and-braces (same guard generation_staging_pilot_run.py uses):
    # refuse before a session is ever constructed if the configured DB is
    # not local.
    assert_local_database_target(str(engine.url))

    async with AsyncSessionLocal() as session:
        generation_caller = build_mcq_factory_generation_caller(session, settings=settings)
        verification_caller = build_mcq_factory_verification_caller(session, settings=settings)
        taxonomy_resolver = await build_taxonomy_resolver_from_session(session)

        async def staging_writer(record: Any) -> bool:
            # The ONLY write path reachable from this CLI: the approved,
            # local-DB-only, non-production generation_staging.candidates
            # table. Never cms.content_items, never any other table, never
            # an auto-publish.
            #
            # MCQ-FACTORY-STAGING-ROLLBACK-001 (2026-10-14): orchestrator's
            # ``_finalize`` catches any exception this raises into
            # ``record.staging_write_ok=False`` WITHOUT rolling back — by
            # design, so one bad record never crashes the whole batch. But
            # on a real SQLAlchemy failure (e.g. a column-length/encoding
            # violation) the shared AsyncSession is left in "pending
            # rollback": every later commit() on THIS session then also
            # raises, even for perfectly valid records — a silent cascade.
            # Proven live: a real syllabus-driven run recorded 237
            # checkpoint entries but only persisted 111 staging rows before
            # this fix. Rolling back here (before re-raising, so
            # ``_finalize``'s own bookkeeping/behavior is unchanged)
            # restores the session so the NEXT fact's write isn't poisoned
            # by this one's failure.
            try:
                ok = await insert_staging_candidate(session, record)
                await session.commit()
                return ok
            except Exception:
                await session.rollback()
                raise

        async def cross_batch_duplicate_lookup(stem_hash_value: str) -> list[CrossBatchDuplicateMatch]:
            # Real, fresh read of generation_staging.candidates across ALL
            # prior batches on every call — never a stale snapshot. See
            # the module docstring above for the structural gap this
            # fixes.
            matches = await find_staging_candidates_by_stem_hash(session, stem_hash_value)
            return [
                CrossBatchDuplicateMatch(
                    staging_id=m.staging_id,
                    batch_id=m.batch_id,
                    fact_id=m.fact_id,
                    attempt_number=m.attempt_number,
                )
                for m in matches
            ]

        yield LiveDependencies(
            session=session,
            generation_caller=generation_caller,
            verification_caller=verification_caller,
            taxonomy_resolver=taxonomy_resolver,
            staging_writer=staging_writer,
            publication_gate_session=session,
            cross_batch_duplicate_lookup=cross_batch_duplicate_lookup,
        )


# ---------------------------------------------------------------------------
# Provider-aware limits resolution — shared by the dry-run plan display
# (main()) and the real live run (run_live()) so the two can never drift:
# the token caps print_plan shows are EXACTLY the ones a live run with the
# same --budget-profile would actually use.
# ---------------------------------------------------------------------------


def _resolve_limits(args: argparse.Namespace, settings: Any):
    """Resolve (limits, generation_selection, verification_selection) for
    this CLI invocation. ``limits`` uses
    ``GroqFactoryLimits.from_stage_selections`` /
    ``pilot_profile_for_stage_selections`` (NEET-MCQ-FACTORY-OPENROUTER-
    PRODUCTIONIZED-20261013) — per-(provider, model) token caps, e.g. the
    much higher cap OpenRouter's nemotron reasoning model needs — instead
    of always reading Groq's settings fields regardless of which provider
    this run actually resolves to. Groq's own numbers are unchanged: when
    no (provider, model)-specific profile is registered (the case for
    Groq's models), this falls back to exactly the existing
    ``mcq_factory_groq_max_generation_tokens`` / ``_max_verification_tokens``
    values, same as before this change."""
    from app.modules.cms.services.mcq_factory_groq_controls import GroqFactoryLimits
    from app.modules.cms.services.mcq_llm_provider import resolve_mcq_factory_stage_selection

    gen_selection = resolve_mcq_factory_stage_selection("generation", settings=settings)
    verify_selection = resolve_mcq_factory_stage_selection("verification", settings=settings)

    kwargs = dict(
        generation_provider=gen_selection.registry_name,
        generation_model=gen_selection.model,
        verification_provider=verify_selection.registry_name,
        verification_model=verify_selection.model,
        settings=settings,
    )
    limits = (
        GroqFactoryLimits.pilot_profile_for_stage_selections(**kwargs)
        if args.budget_profile == "pilot"
        else GroqFactoryLimits.from_stage_selections(**kwargs)
    )
    return limits, gen_selection, verify_selection


# ---------------------------------------------------------------------------
# Live run — thin invocation of GroqFactoryOrchestrator
# ---------------------------------------------------------------------------


async def run_live(
    args: argparse.Namespace,
    settings: Any,
    *,
    dependencies_factory: DependenciesFactory = default_live_dependencies,
) -> int:
    """Thin invocation layer: build FactSpecs + index the evidence PDF,
    construct a ``GroqFactoryOrchestrator`` from EXISTING components only
    (via ``dependencies_factory``), and call ``run_batch``. Never
    re-implements budget/rate/retry/validation/publication-gate logic —
    all of that lives in ``orchestrator.py`` / ``mcq_factory_groq_controls.py``
    / ``validators.py`` and is reused unmodified."""
    from app.modules.cms.mcq_factory_groq.orchestrator import GroqFactoryOrchestrator
    from app.modules.cms.mcq_factory_groq.pdf_text_index import index_pdf
    from app.modules.cms.services.mcq_factory_groq_controls import GroqFactoryCheckpoint

    try:
        _check_required_live_config(settings)
        if args.fact_pack is None:
            raise CliConfigError("--fact-pack is required for a live run.")
        if args.evidence_pdf is None:
            raise CliConfigError("--evidence-pdf is required for a live run.")
        fact_specs = _load_fact_specs(args.fact_pack)
        if args.count is not None and args.count > 0:
            fact_specs = fact_specs[: args.count]
        document = index_pdf(args.evidence_pdf)
    except (CliConfigError, FileNotFoundError) as exc:
        print(f"REFUSING TO RUN LIVE: {exc}", file=sys.stderr)
        return 4

    limits, gen_selection, verify_selection = _resolve_limits(args, settings)
    checkpoint = GroqFactoryCheckpoint(args.checkpoint_path, batch_id=args.batch_id)

    print(
        f"[live] batch_id={args.batch_id} facts={len(fact_specs)} "
        f"budget_profile={args.budget_profile} spend_ceiling_usd={limits.max_total_spend_usd}"
    )
    print(
        f"[live] generation={gen_selection.registry_name}:{gen_selection.model} "
        f"(max_tokens={limits.max_generation_tokens_per_question}) "
        f"verification={verify_selection.registry_name}:{verify_selection.model} "
        f"(max_tokens={limits.max_verification_tokens_per_question})"
    )

    async with dependencies_factory(settings) as deps:
        orchestrator = GroqFactoryOrchestrator(
            batch_id=args.batch_id,
            limits=limits,
            checkpoint=checkpoint,
            generation_caller=deps.generation_caller,
            generation_provider_name=gen_selection.registry_name,
            generation_model=gen_selection.model,
            verification_caller=deps.verification_caller,
            verification_provider_name=verify_selection.registry_name,
            verification_model=verify_selection.model,
            taxonomy_resolver=deps.taxonomy_resolver,
            staging_writer=deps.staging_writer,
            publication_gate_session=deps.publication_gate_session,
            cross_batch_duplicate_lookup=deps.cross_batch_duplicate_lookup,
        )
        results = await orchestrator.run_batch(
            fact_specs, document, max_attempts_per_fact=args.max_attempts_per_fact
        )

    accepted = sum(1 for r in results if r.status == "ACCEPTED")
    review_required = sum(1 for r in results if r.status == "REVIEW_REQUIRED")
    rejected = sum(1 for r in results if r.status == "REJECTED")
    total_cost = sum(r.total_cost_usd for r in results)
    budget_stopped_early = len(results) < len(fact_specs)

    print(f"[live] processed {len(results)}/{len(fact_specs)} facts")
    print(f"[live]   accepted={accepted} review_required={review_required} rejected={rejected}")
    print(
        f"[live]   total_cost_usd_this_process={total_cost:.4f} "
        f"cumulative_checkpoint_spend_usd={checkpoint.total_spent_usd():.4f} "
        f"ceiling_usd={limits.max_total_spend_usd:.4f}"
    )
    if budget_stopped_early:
        print(
            "[live] BUDGET CEILING REACHED — batch stopped early without exceeding the cap. "
            "Re-run the same command (same --checkpoint-path) to resume: already-processed "
            "facts are skipped via the checkpoint and are never re-spent.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Importing settings/limits is pure config (pydantic-settings reading
    # env vars) — it never constructs an HTTP client or AIProvider.
    from app.core.config import get_settings

    settings = get_settings()
    # NEET-MCQ-FACTORY-OPENROUTER-PRODUCTIONIZED-20261013: resolved via the
    # same provider-aware helper run_live() uses, so the dry-run plan ALWAYS
    # shows the real token caps/provider a live run with the same
    # --budget-profile would actually use — never drifts from it.
    limits, _gen_selection, _verify_selection = _resolve_limits(args, settings)

    if args.dry_run:
        print_plan(args, limits)
        return 0

    if not args.live_opt_in:
        print_plan(args, limits)
        print(
            "\nRefusing to run live: --i-understand-this-calls-a-live-paid-api was not "
            "passed. This is the required, explicit opt-in and defaults to off.",
            file=sys.stderr,
        )
        return 2

    # --- LIVE PATH -----------------------------------------------------
    # Reachable only with BOTH --no-dry-run AND the opt-in flag. Fails
    # CLOSED on missing/invalid config (GROQ_API_KEY, GROQ_ENABLED,
    # provider selection) or missing/malformed --fact-pack/--evidence-pdf
    # before constructing anything real — see run_live/_check_required_live_config.
    return asyncio.run(run_live(args, settings))


if __name__ == "__main__":
    raise SystemExit(main())
