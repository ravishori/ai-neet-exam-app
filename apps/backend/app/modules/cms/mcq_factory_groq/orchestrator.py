"""MCQ-FACTORY-GROQ-ORCHESTRATOR-001 — end-to-end coordination layer.

Thin coordinator ONLY. Every real piece of work is delegated to an
existing module — this file never re-implements validation, budget/rate/
retry rails, or publication gating:

    pdf-index (pdf_text_index.index_pdf)
        -> evidence-select (evidence_selector.select_evidence_chunk)
        -> syllabus gate (syllabus_gate.check_generation_topic_in_syllabus)
        -> GENERATION call (openai/gpt-oss-20b, via an injected caller)
        -> VERIFICATION call (openai/gpt-oss-120b, via a SEPARATE injected
           caller — see mcq_llm_provider.GatewayMcqVerificationProvider)
        -> deterministic validation (validators.run_deterministic_validation_pipeline,
           which itself calls factory_qa_gates / factory_v2_answer_ambiguity /
           numerical_validation unmodified)
        -> REAL publication_gates.evaluate_question_publication_gates
           (via validators.evaluate_publication_readiness, unmodified)
        -> staging-store persistence (generation_staging_store.insert_staging_candidate,
           via an injectable writer so tests never touch a real database)

Every call that could ever cost money is routed through
``mcq_factory_groq_controls.py``'s ``SpendTracker`` / ``RetryBudget`` /
``SlidingWindowRateLimiter`` / ``GroqFactoryCheckpoint`` — this module
never bypasses them and never constructs an HTTP client itself. Callers
inject plain async callables (``GenerationCaller`` / ``VerificationCaller``
below) — see ``build_groq_generation_caller`` / ``build_groq_verification_caller``
for the production wiring that adapts ``GatewayMcqLlmProvider.generate_mcq`` /
``GatewayMcqVerificationProvider.verify_candidate`` into that shape, and
any test file for how trivially a fake async function satisfies the same
shape with zero network calls.

ROUTING RULE (never overridable — see ``_decide_status`` below): a
candidate is forced to ``REVIEW_REQUIRED`` whenever the independent
verification call disagrees with the generated answer, reports
insufficient/unmatchable evidence (including when verification could not
be run or could not be parsed at all — treated identically to
"insufficient", never treated as implicit agreement), or ANY deterministic
check (structure, taxonomy, provenance/citation relocation, ambiguity,
numerical, safety, or the real publication-gates ``content_ready``) does
not come back clean. Only a fully-clean run is ``ACCEPTED``. Nothing in
this module (and nothing any caller passes in) can flip a forced
``REVIEW_REQUIRED`` back to ``ACCEPTED``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from pydantic import ValidationError

from app.modules.ai.gateway.base import AIResponse, ProviderError
from app.modules.ai.gateway.pricing import estimate_cost
from app.modules.cms.mcq_factory_groq.evidence_selector import EvidenceChunk, select_evidence_chunk
from app.modules.cms.mcq_factory_groq.pdf_text_index import IndexedDocument
from app.modules.cms.mcq_factory_groq.prompt_templates import (
    GENERATION_SYSTEM_PROMPT,
    GENERATION_USER_PROMPT_TEMPLATE,
    VERIFICATION_SYSTEM_PROMPT,
    VERIFICATION_USER_PROMPT_TEMPLATE,
    angle_for_attempt,
)
from app.modules.cms.mcq_factory_groq.schemas import GeneratedMcqCandidate, TaxonomyIds
from app.modules.cms.mcq_factory_groq.syllabus_gate import check_generation_topic_in_syllabus
from app.modules.cms.syllabus.neet_2026_parser import NeetSyllabusRegistry
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash
from app.modules.cms.mcq_factory_groq.validators import (
    CorpusAnswerRecord,
    DuplicateCandidateSnapshot,
    FactoryValidationReport,
    TaxonomyResolver,
    VerificationVerdict,
    evaluate_publication_readiness,
    run_deterministic_validation_pipeline,
)
from app.modules.cms.services.mcq_factory_groq_controls import (
    CheckpointEntry,
    GroqFactoryCheckpoint,
    GroqFactoryLimits,
    RetryBudget,
    RetryBudgetExceeded,
    SlidingWindowRateLimiter,
    SpendCeilingExceeded,
    SpendTracker,
    enforce_token_cap,
)
from app.modules.cms.services.mcq_llm_provider import classify_mcq_error, is_retryable_provider_error

logger = logging.getLogger(__name__)

# Terminal statuses this orchestrator ever assigns to a fully-processed
# candidate. "REJECTED" is reserved for pipeline-level stops BEFORE a
# candidate exists to validate (out-of-syllabus, no groundable evidence,
# a generation call that never produced usable output after retries).
# "REVIEW_REQUIRED" means a candidate DID get produced but something in
# the routing rule above fired. "ACCEPTED" means a fully clean run.
STATUS_ACCEPTED = "ACCEPTED"
STATUS_REJECTED = "REJECTED"
STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"

# NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: a distinguishable REASON string (the
# status itself stays STATUS_REJECTED — "reason-independent of which angle
# was requested" per the multi-attempt plan §3.4) recorded on an attempt
# that was never dispatched because the immediately preceding attempt on
# the same fact was REJECTED. Zero-cost, zero-spend: no provider call, no
# checkpoint write, no staging write — see run_batch below.
REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED = "SKIPPED_PRIOR_ATTEMPT_REJECTED"


class CandidateParseError(RuntimeError):
    """Raised when a model response cannot be parsed into the expected
    JSON shape — malformed JSON or a schema/field validation failure.
    Always caught by this module; never escapes ``process_fact``."""


# ---------------------------------------------------------------------------
# Caller protocol — production wiring adapts the existing façades to this;
# tests pass trivial async functions. Neither side needs to know about the
# other's AIGateway/session plumbing.
# ---------------------------------------------------------------------------


class LlmCaller(Protocol):
    async def __call__(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse: ...


GenerationCaller = Callable[..., Awaitable[AIResponse]]
VerificationCaller = Callable[..., Awaitable[AIResponse]]
StagingWriter = Callable[[Any], Awaitable[bool]]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class CrossBatchDuplicateMatch:
    """One real ``generation_staging.candidates`` row (ANY prior batch)
    whose ``stem_hash`` exactly matches a new candidate's — see
    ``generation_staging_store.find_staging_candidates_by_stem_hash``,
    the production implementation this shape adapts. Plain data only;
    this module never queries a database itself."""

    staging_id: str
    batch_id: str
    fact_id: str
    attempt_number: int


# Injected, async, read-only cross-BATCH duplicate lookup: given a
# candidate's ``stem_hash`` (from ``factory_candidate_validation.stem_hash``),
# return every prior-batch staging row with that exact hash. ``None`` (the
# default — see ``GroqFactoryOrchestrator.__init__``) means this check is
# simply skipped, which is the correct, backward-compatible behavior for
# any existing caller that does not wire a real lookup — the cross-ATTEMPT
# (in-memory, current-run) check still runs regardless, since it requires
# no I/O at all.
CrossBatchDuplicateLookup = Callable[[str], Awaitable[list[CrossBatchDuplicateMatch]]]


async def _default_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


# ---------------------------------------------------------------------------
# Per-fact static inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FactSpec:
    fact_id: str
    subject: str
    unit_number: int
    chapter: str
    topic: str
    class_level: str
    taxonomy: TaxonomyIds
    concept: str | None = None
    unit_name: str | None = None
    academic_subject_code: str | None = None
    calculation_check: dict[str, Any] | None = None
    # Injectable syllabus registry (defaults to the real, authoritative
    # NEETSyllabus.txt via check_generation_topic_in_syllabus's own
    # default when left None). Tests pass a small fixture registry here
    # instead of depending on the real syllabus file's exact wording.
    syllabus_registry: NeetSyllabusRegistry | None = None
    # NEET-MCQ-FACTORY-TOPIC-MAPPING-FIX-20261012: deterministic, reviewed
    # syllabus-registry topic_id (e.g. "BIOLOGY:U03:T01") for this fact's
    # fine-grained concept/topic — a DIFFERENT id system than
    # ``taxonomy.topic_id`` (that one is a real academic-DB UUID; this one
    # is the syllabus registry's own id, assigned from
    # docs/quality/neet_mcq_factory_TOPIC_MAPPING_FIX_20261012.json after
    # confirming the fact's concept is a genuine documented sub-item of
    # that syllabus topic block's text). When set, it lets
    # check_generation_topic_in_syllabus authorize via its existing
    # exact topic_id match path instead of requiring the fact's
    # free-text ``topic`` to exact-string-match an entire semicolon-joined
    # syllabus block. When None (no confirmed mapping), the gate falls
    # back to the free-text ``topic`` exact-match path exactly as before
    # — never fuzzy-matched, never force-authorized.
    syllabus_topic_id: str | None = None


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@dataclass
class ModelCallAudit:
    stage: str  # "generation" | "verification"
    attempt_no: int
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    status: str = "SUCCESS"  # "SUCCESS" | "ERROR"
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "attempt_no": self.attempt_no,
            "model": self.model,
            "provider": self.provider,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
            "status": self.status,
            "error_code": self.error_code,
        }


@dataclass
class CandidateAuditRecord:
    fact_id: str
    batch_id: str
    attempt_number: int
    status: str
    reason: str
    model_calls: list[ModelCallAudit] = field(default_factory=list)
    candidate: GeneratedMcqCandidate | None = None
    verification: VerificationVerdict | None = None
    validation_report: FactoryValidationReport | None = None
    publication_content_ready: bool | None = None
    publication_reasons: list[str] = field(default_factory=list)
    evidence_chunk: EvidenceChunk | None = None
    staging_write_ok: bool | None = None
    staging_write_error: str | None = None
    resumed_skip: bool = False
    # NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: the deterministic angle name
    # (DEFINE_IDENTIFY / COMPARE_CONTRAST / APPLY_SCENARIO /
    # CAUSAL_NUMERIC_STEP) this attempt's generation prompt used — set by
    # ``_finalize`` from ``attempt_number`` alone (see
    # ``prompt_templates.angle_for_attempt``), so it is always populated
    # even for a pipeline-level REJECTED record (useful for the batch
    # report's "angles_used" per-fact breakdown).
    angle_name: str = ""

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.model_calls)


# ---------------------------------------------------------------------------
# Parsing helpers — never trust the model's JSON on its own confidence
# ---------------------------------------------------------------------------


def _parse_generated_candidate(text: str) -> GeneratedMcqCandidate:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CandidateParseError(f"GENERATION_MALFORMED_JSON:{exc}") from exc
    try:
        return GeneratedMcqCandidate.model_validate(payload)
    except ValidationError as exc:
        raise CandidateParseError(f"GENERATION_SCHEMA_INVALID:{exc}") from exc


def _parse_verification_verdict(text: str) -> VerificationVerdict:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CandidateParseError(f"VERIFICATION_MALFORMED_JSON:{exc}") from exc
    if not isinstance(payload, dict):
        raise CandidateParseError("VERIFICATION_MALFORMED_JSON:not_an_object")
    try:
        return VerificationVerdict(
            answer_supported=bool(payload.get("answer_supported", False)),
            ambiguous=bool(payload.get("ambiguous", False)),
            unsupported_claims=list(payload.get("unsupported_claims") or []),
            notes=str(payload.get("notes") or ""),
        )
    except (TypeError, ValueError) as exc:
        raise CandidateParseError(f"VERIFICATION_SCHEMA_INVALID:{exc}") from exc


def _truncation_diagnostic(*, response: AIResponse, token_cap: int) -> str | None:
    """Return a short, explicit diagnostic suffix when ``response``'s
    reported ``completion_tokens`` hit (or somehow exceeded) the
    ``max_tokens`` cap that was actually requested for this call — a
    strong signal the model's response was cut off mid-generation
    (observed in real life with reasoning models such as OpenRouter's
    nvidia/nemotron-3-super-120b-a12b:free, which burn tokens on invisible
    chain-of-thought before emitting visible output) rather than a
    genuinely malformed response the model produced well under its token
    budget. Returns ``None`` when ``completion_tokens`` is strictly below
    the cap (a different, non-truncation cause of the parse failure).

    NEVER changes the REJECTED/REVIEW_REQUIRED outcome by itself — a
    candidate that fails to parse is unusable either way; this only
    enriches the logged/persisted reason string so a human (or a future
    automated triage) can tell "truncated — raise the cap" apart from
    "the model emitted genuinely malformed JSON well within budget"
    without re-running anything.
    """
    completion_tokens = int(getattr(response, "completion_tokens", 0) or 0)
    if token_cap > 0 and completion_tokens >= token_cap:
        return f"LIKELY_TRUNCATED:completion_tokens={completion_tokens}:max_tokens={token_cap}"
    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class GroqFactoryOrchestrator:
    """Coordinates one Groq-backed NEW QUESTION GENERATION batch.

    Construct ONE instance per batch (it owns an in-memory ``SpendTracker``
    rehydrated from ``checkpoint`` in ``__init__`` so cumulative spend is
    correct even on a resumed process). Call ``process_fact`` once per
    fact, or ``run_batch`` for a whole list.
    """

    def __init__(
        self,
        *,
        batch_id: str,
        limits: GroqFactoryLimits,
        checkpoint: GroqFactoryCheckpoint,
        generation_caller: GenerationCaller,
        generation_provider_name: str,
        generation_model: str,
        verification_caller: VerificationCaller | None,
        verification_provider_name: str,
        verification_model: str,
        taxonomy_resolver: TaxonomyResolver,
        staging_writer: StagingWriter,
        publication_gate_session: Any,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        existing_corpus: list[CorpusAnswerRecord] | None = None,
        cross_batch_duplicate_lookup: CrossBatchDuplicateLookup | None = None,
        sleep_fn: SleepFn = _default_sleep,
    ) -> None:
        self.batch_id = batch_id
        self.limits = limits
        self.checkpoint = checkpoint
        # Resumability: fold whatever this checkpoint already recorded back
        # into the tracker BEFORE any new call is ever considered, so a
        # resumed process can never under-count prior spend and blow
        # through the ceiling. This is the existing
        # GroqFactoryCheckpoint.rehydrated_spend_tracker helper — reused,
        # not reimplemented.
        self.spend_tracker: SpendTracker = checkpoint.rehydrated_spend_tracker(limits.max_total_spend_usd)
        self.generation_caller = generation_caller
        self.generation_provider_name = generation_provider_name
        self.generation_model = generation_model
        self.verification_caller = verification_caller
        self.verification_provider_name = verification_provider_name
        self.verification_model = verification_model
        self.taxonomy_resolver = taxonomy_resolver
        self.staging_writer = staging_writer
        self.publication_gate_session = publication_gate_session
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            requests_per_minute=limits.rate_limit_requests_per_minute,
            tokens_per_minute=limits.rate_limit_tokens_per_minute,
        )
        self.existing_corpus = existing_corpus or []
        # NEET-MCQ-FACTORY-MULTI-ATTEMPT-001 dedup wiring.
        self.cross_batch_duplicate_lookup = cross_batch_duplicate_lookup
        # Cross-ATTEMPT (in-memory, current-run) accepted-candidate
        # snapshots, keyed by fact_id — populated by process_fact
        # immediately after a candidate is decided ACCEPTED (never before:
        # an attempt is only ever compared against EARLIER accepted
        # attempts, never against itself or a later one). NOT the same
        # structure as self.existing_corpus (a separate, pre-batch,
        # whole-corpus concern populated once at construction).
        self._accepted_candidates_by_fact: dict[str, list[DuplicateCandidateSnapshot]] = {}
        self.sleep_fn = sleep_fn

    # -- retried, budget-gated, rate-limited single logical call ---------

    async def _call_with_retries(
        self,
        *,
        stage: str,
        caller: Callable[..., Awaitable[AIResponse]],
        provider_name: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        token_cap: int,
    ) -> tuple[AIResponse, list[ModelCallAudit]]:
        retry_budget = RetryBudget(max_retries=self.limits.max_retries_per_call)
        calls: list[ModelCallAudit] = []
        attempt_no = 0
        max_tokens = enforce_token_cap(requested_max_tokens=token_cap, cap=token_cap, stage=stage)

        while True:
            attempt_no += 1

            # Pre-dispatch budget check — runs before the FIRST attempt AND
            # before every retry attempt, per the hard safety contract.
            # Conservative worst case: assume both prompt and completion
            # tokens hit the configured cap, so a call is refused BEFORE
            # it is ever dispatched if even the worst case would breach
            # the ceiling — never only checked after the fact.
            worst_case = estimate_cost(provider_name, model, token_cap, token_cap).cost_usd
            if self.spend_tracker.would_exceed(worst_case):
                budget_exc = SpendCeilingExceeded(
                    f"{stage} attempt {attempt_no} for model={model} refused BEFORE dispatch: "
                    f"worst-case cost ${worst_case:.4f} would exceed the "
                    f"${self.limits.max_total_spend_usd:.4f} ceiling "
                    f"(already spent ${self.spend_tracker.spent_usd:.4f})."
                )
                budget_exc.partial_calls = calls  # type: ignore[attr-defined]
                raise budget_exc

            wait_s = self.rate_limiter.wait_time_s(tokens=max_tokens)
            if wait_s > 0:
                await self.sleep_fn(wait_s)

            try:
                response = await caller(
                    system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens
                )
            except Exception as exc:  # noqa: BLE001 — classify everything, never leak raw exceptions
                provider_error = classify_mcq_error(exc, provider=provider_name)
                calls.append(
                    ModelCallAudit(
                        stage=stage,
                        attempt_no=attempt_no,
                        model=model,
                        provider=provider_name,
                        status="ERROR",
                        error_code=provider_error.code,
                    )
                )
                if not is_retryable_provider_error(provider_error):
                    provider_error.partial_calls = calls  # type: ignore[attr-defined]
                    raise provider_error
                # Bounded retries: consume() itself raises RetryBudgetExceeded
                # once exhausted — this loop never retries unboundedly.
                try:
                    retry_budget.consume()
                except RetryBudgetExceeded as rbe:
                    rbe.partial_calls = calls  # type: ignore[attr-defined]
                    raise
                continue

            self.rate_limiter.record(tokens=max(response.total_tokens, response.prompt_tokens + response.completion_tokens))
            cost = estimate_cost(provider_name, model, response.prompt_tokens, response.completion_tokens)
            response.cost_usd = cost.cost_usd
            response.cost_status = cost.cost_status
            # Backstop: even though the worst-case pre-check above already
            # guarded against this, record() re-validates against the
            # ACTUAL cost and would still raise if something upstream
            # mis-estimated — spend is never silently allowed over budget.
            self.spend_tracker.record(cost.cost_usd)
            calls.append(
                ModelCallAudit(
                    stage=stage,
                    attempt_no=attempt_no,
                    model=model,
                    provider=provider_name,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    cost_usd=cost.cost_usd,
                    status="SUCCESS",
                )
            )
            return response, calls

    # -- one fact end to end ----------------------------------------------

    async def process_fact(
        self,
        spec: FactSpec,
        document: IndexedDocument,
        *,
        sequence_in_batch: int = 1,
        attempt_number: int = 1,
    ) -> CandidateAuditRecord:
        # Resumability / idempotency: a key already recorded by a prior
        # (possibly crashed) run is never reprocessed and never re-spent.
        if self.checkpoint.is_done(spec.fact_id, attempt_number):
            entry = self.checkpoint.get(spec.fact_id, attempt_number)
            status = entry.status if entry else STATUS_REJECTED
            return CandidateAuditRecord(
                fact_id=spec.fact_id,
                batch_id=self.batch_id,
                attempt_number=attempt_number,
                status=status,
                reason="RESUMED_SKIP_ALREADY_PROCESSED",
                resumed_skip=True,
            )

        model_calls: list[ModelCallAudit] = []

        # 1. Syllabus gate — deterministic, zero cost, must run before any
        #    generation call is ever made.
        scope = check_generation_topic_in_syllabus(
            subject=spec.subject,
            unit_number=spec.unit_number,
            # When a deterministic syllabus_topic_id mapping is present,
            # authorize via that exact-match topic_id path alone. The
            # fact's free-text `topic` is a fine-grained sub-concept (e.g.
            # "Cell Structure and Organelles") that will NEVER
            # string-equal the syllabus registry's whole semicolon-joined
            # topic-block text (e.g. "Cell theory...; ...; Nucleus-...") —
            # passing both would make assert_blueprint_neet_syllabus_scope's
            # own topic_text_mismatch check fail this fact for real,
            # correctly-mapped topic_ids. Falls back to the free-text
            # exact-match path (unchanged) when no mapping was confirmed.
            topic=spec.topic if spec.syllabus_topic_id is None else None,
            topic_id=spec.syllabus_topic_id,
            # Same reasoning as `topic` above: fact-pack ``unit_name``
            # values are inconsistent (sometimes an NCERT chapter name
            # like "Human Reproduction", sometimes the syllabus unit name
            # plus a "(Botany)"/"(Zoology)" annotation) and were never
            # the authoritative binding — the registry topic_id already
            # carries its own subject+unit_number, which
            # assert_blueprint_neet_syllabus_scope cross-checks against
            # unit_id internally. Omit this optional, non-authoritative
            # field once topic_id makes it redundant so a mismatched
            # fact-pack label never blocks an otherwise-correct mapping.
            unit_name=spec.unit_name if spec.syllabus_topic_id is None else None,
            academic_subject_code=spec.academic_subject_code,
            registry=spec.syllabus_registry,
        )
        if not scope.is_in_scope:
            return await self._finalize(
                spec=spec,
                sequence_in_batch=sequence_in_batch,
                attempt_number=attempt_number,
                status=STATUS_REJECTED,
                reason=f"OUT_OF_SYLLABUS_SCOPE:status={scope.status}:detail={scope.detail}",
                model_calls=model_calls,
            )

        # 2. Evidence selection — deterministic, zero cost.
        chunk = select_evidence_chunk(document, topic=spec.topic, concept=spec.concept)
        if chunk is None:
            return await self._finalize(
                spec=spec,
                sequence_in_batch=sequence_in_batch,
                attempt_number=attempt_number,
                status=STATUS_REJECTED,
                reason="EVIDENCE_NOT_GROUNDABLE",
                model_calls=model_calls,
            )

        # 3. Generation call (budget/rate/retry-gated).
        # NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: deterministic angle selection
        # is GUIDANCE ONLY for the model, never proof of uniqueness — see
        # prompt_templates.angle_for_attempt's docstring. The actual safety
        # net against near-identical attempts is the cross-attempt/
        # cross-batch dedup check below (step 3.5), not this prompt text.
        _angle_name, angle_instruction = angle_for_attempt(attempt_number)
        user_prompt = GENERATION_USER_PROMPT_TEMPLATE.format(
            subject=spec.subject,
            chapter=spec.chapter,
            topic=spec.topic,
            source_pdf=chunk.source_pdf,
            page_number=chunk.page_number,
            doc_id=chunk.doc_id,
            evidence_text=chunk.text,
            subject_id=spec.taxonomy.subject_id,
            chapter_id=spec.taxonomy.chapter_id,
            topic_id=spec.taxonomy.topic_id,
            concept_id=spec.taxonomy.concept_id or "",
            angle_instruction=angle_instruction,
        )
        try:
            gen_response, gen_calls = await self._call_with_retries(
                stage="generation",
                caller=self.generation_caller,
                provider_name=self.generation_provider_name,
                model=self.generation_model,
                system_prompt=GENERATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                token_cap=self.limits.max_generation_tokens_per_question,
            )
            model_calls.extend(gen_calls)
        except SpendCeilingExceeded as exc:
            model_calls.extend(getattr(exc, "partial_calls", []))
            return await self._finalize(
                spec=spec,
                sequence_in_batch=sequence_in_batch,
                attempt_number=attempt_number,
                status=STATUS_REJECTED,
                reason=f"BUDGET_EXHAUSTED:{exc}",
                model_calls=model_calls,
                evidence_chunk=chunk,
                raise_budget_exceeded=exc,
            )
        except (RetryBudgetExceeded, ProviderError) as exc:
            model_calls.extend(getattr(exc, "partial_calls", []))
            return await self._finalize(
                spec=spec,
                sequence_in_batch=sequence_in_batch,
                attempt_number=attempt_number,
                status=STATUS_REJECTED,
                reason=f"GENERATION_PROVIDER_FAILED:{type(exc).__name__}:{exc}",
                model_calls=model_calls,
                evidence_chunk=chunk,
            )

        try:
            candidate = _parse_generated_candidate(gen_response.text)
        except CandidateParseError as exc:
            reason = str(exc)
            truncation = _truncation_diagnostic(
                response=gen_response, token_cap=self.limits.max_generation_tokens_per_question
            )
            if truncation is not None:
                reason = f"{reason}:{truncation}"
                logger.warning(
                    "mcq_factory_groq.generation.likely_truncated batch_id=%s fact_id=%s "
                    "provider=%s model=%s %s",
                    self.batch_id, spec.fact_id, self.generation_provider_name, self.generation_model, truncation,
                )
            return await self._finalize(
                spec=spec,
                sequence_in_batch=sequence_in_batch,
                attempt_number=attempt_number,
                status=STATUS_REJECTED,
                reason=reason,
                model_calls=model_calls,
                evidence_chunk=chunk,
            )

        # 4. Verification call — a GENUINELY SEPARATE call site/model.
        #    A missing/unavailable/unparsable verification result is
        #    treated as "insufficient" (never as implicit agreement) —
        #    the routing rule below forces REVIEW_REQUIRED either way.
        verification: VerificationVerdict | None = None
        verification_parse_issue: str | None = None
        if self.verification_caller is not None:
            verify_user_prompt = VERIFICATION_USER_PROMPT_TEMPLATE.format(
                evidence_text=chunk.text,
                stem=candidate.stem,
                options=json.dumps([{"label": o.label, "text": o.text} for o in candidate.options]),
                correct_option=candidate.correct_option,
                explanation=candidate.explanation,
            )
            try:
                verify_response, verify_calls = await self._call_with_retries(
                    stage="verification",
                    caller=self.verification_caller,
                    provider_name=self.verification_provider_name,
                    model=self.verification_model,
                    system_prompt=VERIFICATION_SYSTEM_PROMPT,
                    user_prompt=verify_user_prompt,
                    token_cap=self.limits.max_verification_tokens_per_question,
                )
            except SpendCeilingExceeded as exc:
                model_calls.extend(getattr(exc, "partial_calls", []))
                return await self._finalize(
                    spec=spec,
                    sequence_in_batch=sequence_in_batch,
                    attempt_number=attempt_number,
                    status=STATUS_REJECTED,
                    reason=f"BUDGET_EXHAUSTED:{exc}",
                    model_calls=model_calls,
                    evidence_chunk=chunk,
                    candidate=candidate,
                    raise_budget_exceeded=exc,
                )
            except (RetryBudgetExceeded, ProviderError) as exc:
                # Provider failure is "handled safely": the candidate is
                # NOT discarded, it is simply treated as unverified
                # (verification stays None), which the routing rule below
                # forces to REVIEW_REQUIRED — never implicit agreement.
                model_calls.extend(getattr(exc, "partial_calls", []))
                verification = None
            else:
                model_calls.extend(verify_calls)
                try:
                    verification = _parse_verification_verdict(verify_response.text)
                except CandidateParseError as exc:
                    # Malformed verification JSON — same "insufficient,
                    # never implicit agreement" treatment as a provider
                    # failure above. Still never implicitly accepted; this
                    # only annotates WHY verification was unavailable, the
                    # same truncation-vs-genuinely-malformed distinction
                    # applied to generation above.
                    verification = None
                    truncation = _truncation_diagnostic(
                        response=verify_response, token_cap=self.limits.max_verification_tokens_per_question
                    )
                    verification_parse_issue = str(exc) + (f":{truncation}" if truncation else "")
                    if truncation is not None:
                        logger.warning(
                            "mcq_factory_groq.verification.likely_truncated batch_id=%s fact_id=%s "
                            "provider=%s model=%s %s",
                            self.batch_id, spec.fact_id, self.verification_provider_name, self.verification_model, truncation,
                        )

        # 4.5 Cross-attempt / cross-batch TRUE DUPLICATE detection
        #     (NEET-MCQ-FACTORY-MULTI-ATTEMPT-001 — the real fix for the
        #     "existing_corpus is a stale, never-updated snapshot and the
        #     real CLI never even populates it" structural gap). Pre-fetch
        #     BOTH signals as plain data BEFORE calling the (synchronous,
        #     I/O-free) validators pipeline:
        #       (a) cross-attempt: earlier ACCEPTED attempts on this SAME
        #           fact_id, in-memory, this run only.
        #       (b) cross-batch: a REAL, fresh read of
        #           generation_staging.candidates across ALL prior
        #           batches, via the injected cross_batch_duplicate_lookup
        #           (None by default -> this signal is simply skipped,
        #           never fabricated).
        prior_candidates_for_duplicate_check = list(
            self._accepted_candidates_by_fact.get(spec.fact_id, [])
        )
        if self.cross_batch_duplicate_lookup is not None:
            cand_stem_hash = stem_hash(candidate.stem)
            try:
                cross_batch_matches = await self.cross_batch_duplicate_lookup(cand_stem_hash)
            except Exception:  # noqa: BLE001 — a dedup-lookup failure must never crash the batch
                logger.warning(
                    "mcq_factory_groq.cross_batch_duplicate_lookup.failed batch_id=%s fact_id=%s",
                    self.batch_id, spec.fact_id, exc_info=True,
                )
                cross_batch_matches = []
            prior_candidates_for_duplicate_check.extend(
                DuplicateCandidateSnapshot(
                    source=(
                        f"staging:{m.batch_id}:{m.fact_id}:attempt{m.attempt_number}:id={m.staging_id}"
                    ),
                    stem_hash_value=cand_stem_hash,
                )
                for m in cross_batch_matches
            )

        # 5. Deterministic validation (structure/taxonomy/provenance/
        #    ambiguity/numerical/safety/cross-attempt-duplicate/
        #    reviewer-gate), including the REAL publication_gates call.
        report = run_deterministic_validation_pipeline(
            candidate,
            document=document,
            taxonomy_resolver=self.taxonomy_resolver,
            existing_corpus=self.existing_corpus,
            calculation_check=spec.calculation_check,
            verification=verification,
            prior_candidates_for_duplicate_check=prior_candidates_for_duplicate_check,
        )

        provenance_relocated_ok = any(
            g.code == "P_PROVENANCE" and g.passed for g in report.gates
        )
        ncert_evidence = _build_truthful_ncert_evidence(
            spec=spec,
            chunk=chunk,
            relocated_ok=provenance_relocated_ok,
        )
        provenance_block = {
            "origin": "mcq_factory_groq_orchestrator",
            # MCQ-FACTORY-PROVIDER-AGNOSTIC-001 defect fix: this literally
            # read f"groq:{self.generation_provider_name}:{self.generation_model}"
            # before — a hard-coded "groq:" prefix regardless of
            # self.generation_provider_name's actual value, so a batch run
            # with a non-Groq generation provider would have persisted a
            # misleading "groq:openai:gpt-4o-mini"-style source string into
            # every staged candidate's provenance. self.generation_provider_name
            # already carries the real registry name (see
            # GroqFactoryOrchestrator.__init__) — use it alone, with no
            # vendor literal baked in, so this stays correct for whichever
            # provider this orchestrator instance was actually constructed
            # with (Groq remains the default elsewhere; this module itself
            # never assumes it).
            "source": f"{self.generation_provider_name}:{self.generation_model}",
            "batch_id": self.batch_id,
            "validation_process": "mcq_factory_groq.validators.run_deterministic_validation_pipeline",
            "verification_process": self.verification_model if verification is not None else "UNAVAILABLE",
            "class_level": spec.class_level,
            "chapter": spec.chapter,
        }
        pub_report = await evaluate_publication_readiness(
            self.publication_gate_session,
            candidate,
            ncert_evidence=ncert_evidence,
            provenance=provenance_block,
            tags=[],
        )

        status = _decide_status(report=report, verification=verification, pub_content_ready=pub_report.content_ready)

        if status == STATUS_ACCEPTED:
            # Record THIS attempt's snapshot only AFTER it was decided
            # ACCEPTED, and only now (never before this point) — so a
            # later attempt on the same fact is compared against every
            # EARLIER accepted attempt, and this attempt never compares
            # against itself.
            self._accepted_candidates_by_fact.setdefault(spec.fact_id, []).append(
                DuplicateCandidateSnapshot(
                    source=f"staging:{self.batch_id}:{spec.fact_id}:attempt{attempt_number}",
                    stem_hash_value=stem_hash(candidate.stem),
                    option_texts_norm=tuple(normalize_stem(o.text) for o in candidate.options),
                )
            )

        final_reason = f"classification={report.classification}:publication_content_ready={pub_report.content_ready}"
        if verification_parse_issue is not None:
            # Diagnostic-only addition (see _truncation_diagnostic) — never
            # changes `status` above, which was already decided from
            # verification=None (treated as insufficient) exactly as
            # before this change.
            final_reason = f"{final_reason}:verification_parse_issue={verification_parse_issue}"

        return await self._finalize(
            spec=spec,
            sequence_in_batch=sequence_in_batch,
            attempt_number=attempt_number,
            status=status,
            reason=final_reason,
            model_calls=model_calls,
            evidence_chunk=chunk,
            candidate=candidate,
            verification=verification,
            validation_report=report,
            publication_content_ready=pub_report.content_ready,
            publication_reasons=list(pub_report.reasons),
        )

    # -- finalize: persist audit trail + checkpoint -----------------------

    async def _finalize(
        self,
        *,
        spec: FactSpec,
        sequence_in_batch: int,
        attempt_number: int,
        status: str,
        reason: str,
        model_calls: list[ModelCallAudit],
        evidence_chunk: EvidenceChunk | None = None,
        candidate: GeneratedMcqCandidate | None = None,
        verification: VerificationVerdict | None = None,
        validation_report: FactoryValidationReport | None = None,
        publication_content_ready: bool | None = None,
        publication_reasons: list[str] | None = None,
        raise_budget_exceeded: SpendCeilingExceeded | None = None,
    ) -> CandidateAuditRecord:
        record = CandidateAuditRecord(
            fact_id=spec.fact_id,
            batch_id=self.batch_id,
            attempt_number=attempt_number,
            status=status,
            reason=reason,
            model_calls=model_calls,
            candidate=candidate,
            verification=verification,
            validation_report=validation_report,
            publication_content_ready=publication_content_ready,
            publication_reasons=publication_reasons or [],
            evidence_chunk=evidence_chunk,
        )
        # NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: angle_name is a pure function
        # of attempt_number alone (see prompt_templates.angle_for_attempt)
        # — computed here, once, so every _finalize call site (including
        # pipeline-level REJECTED paths that never reached generation)
        # records it, with zero extra parameters threaded through
        # process_fact's many early-return call sites.
        record.angle_name, _ = angle_for_attempt(attempt_number)

        staging_record = _build_staging_record(spec=spec, sequence_in_batch=sequence_in_batch, record=record)
        try:
            await self.staging_writer(staging_record)
            record.staging_write_ok = True
        except Exception as exc:  # noqa: BLE001 — a staging write failure must never crash the batch
            record.staging_write_ok = False
            record.staging_write_error = f"{type(exc).__name__}: {exc}"[:500]

        # Checkpoint is recorded regardless of staging-write outcome — the
        # checkpoint's job is preventing double-spend on resume, which must
        # hold even if persistence to the staging store failed. A failed
        # staging write is surfaced via record.staging_write_ok/_error for
        # the caller to reconcile (the full candidate payload is still in
        # the returned CandidateAuditRecord either way).
        self.checkpoint.record(
            CheckpointEntry(
                fact_id=spec.fact_id,
                attempt_number=attempt_number,
                status=status,
                cost_usd=record.total_cost_usd,
            )
        )

        if raise_budget_exceeded is not None:
            # Re-raise AFTER persisting this fact's own (failed) outcome so
            # a batch-level caller (run_batch) can stop the whole run
            # cleanly without losing this fact's audit trail.
            record.budget_exceeded = True  # type: ignore[attr-defined]
        return record

    # -- batch convenience --------------------------------------------------

    async def run_batch(
        self,
        specs: list[FactSpec],
        document: IndexedDocument,
        *,
        max_attempts_per_fact: int = 1,
    ) -> list[CandidateAuditRecord]:
        """Process each ``FactSpec`` in order against one shared
        ``IndexedDocument``, stopping early (without crashing) the moment
        the spend ceiling is reached. Already-processed facts (per the
        checkpoint) are skipped — safe to call again after an
        interruption.

        NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: ``max_attempts_per_fact``
        defaults to ``1`` — a caller that never configures this sees
        BYTE-IDENTICAL behavior to before this parameter existed: exactly
        one ``process_fact`` call per fact, at ``attempt_number=1``.

        Sequencing policy for ``max_attempts_per_fact > 1`` (see
        docs/quality/neet_mcq_factory_MULTI_ATTEMPT_PLAN_20261013.md §3.4):
          - attempt N is ``REJECTED`` (a pipeline-level stop — out-of-
            syllabus, no groundable evidence, or a generation call that
            never produced usable output after retries) => every later
            attempt on that SAME fact is SKIPPED, not dispatched. A
            ``REJECTED`` outcome at this stage is a property of the FACT
            itself, computed identically regardless of attempt_number/
            angle — retrying would deterministically fail again for zero
            chance of a different outcome, burning spend for nothing.
          - attempt N is ``REVIEW_REQUIRED`` or ``ACCEPTED`` => the NEXT
            attempt (if configured) still proceeds normally — a candidate
            WAS produced; multi-attempt exists precisely to try a
            different angle that might ground more cleanly, or (once
            accepted) to see if a genuinely distinct second accepted
            candidate exists for the same fact.
        A skipped attempt is recorded in the returned list (never silently
        omitted) as ``STATUS_REJECTED`` /
        ``REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED``, with zero model calls
        and zero cost — it is never written to the checkpoint or the
        staging store, since nothing was ever dispatched for it.
        """
        if max_attempts_per_fact < 1:
            raise ValueError("max_attempts_per_fact must be >= 1")

        results: list[CandidateAuditRecord] = []
        for i, spec in enumerate(specs, start=1):
            prior_status: str | None = None
            budget_exceeded = False
            for attempt_number in range(1, max_attempts_per_fact + 1):
                if prior_status == STATUS_REJECTED:
                    results.append(
                        CandidateAuditRecord(
                            fact_id=spec.fact_id,
                            batch_id=self.batch_id,
                            attempt_number=attempt_number,
                            status=STATUS_REJECTED,
                            reason=REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED,
                        )
                    )
                    continue
                record = await self.process_fact(
                    spec, document, sequence_in_batch=i, attempt_number=attempt_number
                )
                results.append(record)
                prior_status = record.status
                if getattr(record, "budget_exceeded", False):
                    budget_exceeded = True
                    break
            if budget_exceeded:
                break
        return results


def _decide_status(
    *, report: FactoryValidationReport, verification: VerificationVerdict | None, pub_content_ready: bool
) -> str:
    """The never-overridable routing rule.

    verification disagrees OR reports insufficient/unmatchable evidence
    (including "could not be run/parsed", which is never treated as
    implicit agreement) OR any deterministic check fails (classification
    is not GREEN, which already folds in the reviewer gate via
    validators.gate_reviewer, OR the real publication-gates
    content_ready is False) => REVIEW_REQUIRED. Otherwise ACCEPTED.
    """
    verification_disagrees_or_insufficient = verification is None or (
        not verification.answer_supported or verification.ambiguous
    )
    deterministic_failed = report.classification != "GREEN" or not pub_content_ready
    if verification_disagrees_or_insufficient or deterministic_failed:
        return STATUS_REVIEW_REQUIRED
    return STATUS_ACCEPTED


def _build_truthful_ncert_evidence(
    *, spec: FactSpec, chunk: EvidenceChunk, relocated_ok: bool
) -> dict[str, Any]:
    """Build the ``NcertEvidence`` payload for the REAL publication-gates
    call, NEVER fabricating a stronger verification level than what the
    deterministic provenance check (``validators.verify_source_evidence_relocatable``)
    actually confirmed. If relocation failed, this truthfully reports
    NOT_VERIFIED (no page_number) rather than claiming PAGE_VERIFIED —
    ``publication_gates`` will then correctly mark ``ncert_ok=False``,
    which the routing rule above already forces to REVIEW_REQUIRED via
    ``content_ready``."""
    if relocated_ok:
        return {
            "verification_level": "PAGE_VERIFIED",
            "source_document": f"NCERT Class {spec.class_level} {spec.subject}",
            "document_version": None,
            "class_level": spec.class_level,
            "chapter": spec.chapter,
            "section": None,
            "page_number": chunk.page_number,
            "source_excerpt": chunk.quoted_snippet,
            "verification_method": "mcq_factory_groq.validators.verify_source_evidence_relocatable",
            "source_pdf_relpath": chunk.source_pdf,
        }
    return {
        "verification_level": "NOT_VERIFIED",
        "source_document": f"NCERT Class {spec.class_level} {spec.subject}",
        "document_version": None,
        "class_level": spec.class_level,
        "chapter": spec.chapter,
        "section": None,
        "page_number": None,
        "source_excerpt": None,
        "verification_method": "mcq_factory_groq.validators.verify_source_evidence_relocatable:NOT_RELOCATED",
        "source_pdf_relpath": chunk.source_pdf,
    }


def _build_staging_record(*, spec: FactSpec, sequence_in_batch: int, record: CandidateAuditRecord) -> Any:
    """Build a ``generation_staging_store.StagingCandidateRecord`` from one
    completed (or pre-generation-rejected) ``CandidateAuditRecord``. Import
    is local to avoid importing SQLAlchemy at module load for callers that
    never persist (e.g. pure-unit tests of ``_decide_status``)."""
    from app.modules.cms.services.generation_staging_store import StagingCandidateRecord

    candidate = record.candidate
    body = candidate.to_question_body_dict() if candidate else None

    # NEET-MCQ-FACTORY-5000-DELIVERY-001 defect fix (schema-readiness audit,
    # 2026-10-12): this previously hardcoded is_duplicate=False unconditionally,
    # discarding the real cross-corpus conflict finding that
    # run_deterministic_validation_pipeline already computes (the
    # C_CROSS_CORPUS_CONFLICT gate, fed by validators.find_cross_corpus_conflicts).
    # That gate's outcome already correctly influences report.classification
    # (-> _decide_status routes a conflict to REVIEW_REQUIRED today, so this
    # was never a safety/routing defect) but the dedicated, directly-queryable
    # is_duplicate / duplicate_matched_source_file columns on the staging row
    # misreported "no duplicate" even when a real conflict was found and
    # recorded in validation_result.gates. Minimal additive fix: read the same
    # gate the classifier already computed and surface it on these columns too,
    # instead of re-deriving or inventing new duplicate-detection logic.
    conflict_gate = next(
        (g for g in (record.validation_report.gates if record.validation_report else []) if g.code == "C_CROSS_CORPUS_CONFLICT"),
        None,
    )
    # NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: the NEW C_CROSS_ATTEMPT_DUPLICATE
    # gate (validators.gate_cross_attempt_duplicate) catches a TRUE
    # duplicate (same stem, regardless of answer) — the real gap this task
    # fixes (see module docstring). It takes priority over the
    # pre-existing C_CROSS_CORPUS_CONFLICT gate below (an answer-conflict
    # finding is a less specific signal than "this already exists").
    cross_attempt_gate = next(
        (
            g
            for g in (record.validation_report.gates if record.validation_report else [])
            if g.code == "C_CROSS_ATTEMPT_DUPLICATE"
        ),
        None,
    )
    is_duplicate_flag = False
    duplicate_matched_source = None
    duplicate_similarity_value: float | None = None
    if cross_attempt_gate and cross_attempt_gate.warnings:
        is_duplicate_flag = True
        # Warning format is "CROSS_ATTEMPT_DUPLICATE_WITH:<source>" where
        # <source> already carries batch_id/fact_id/attempt_number (and a
        # real staging row id for a cross-batch match) — see
        # validators.DuplicateCandidateSnapshot's docstring.
        first_warning = cross_attempt_gate.warnings[0]
        parts = first_warning.split(":", 1)
        duplicate_matched_source = parts[1] if len(parts) >= 2 else first_warning
        near_dup_warnings = cross_attempt_gate.detail.get("near_duplicate_warnings") or []
        if near_dup_warnings:
            try:
                duplicate_similarity_value = float(near_dup_warnings[0].rsplit("=", 1)[1])
            except (ValueError, IndexError):
                duplicate_similarity_value = None
    elif conflict_gate and conflict_gate.warnings:
        is_duplicate_flag = True
        # Warning format is "ANSWER_CONFLICT_WITH:<source>:existing_answer=...'"
        # (validators.find_cross_corpus_conflicts) — extract <source> only;
        # fall back to the raw warning text if the format ever changes.
        first_warning = conflict_gate.warnings[0]
        parts = first_warning.split(":", 2)
        duplicate_matched_source = parts[1] if len(parts) >= 2 else first_warning
    validation_result = {
        "gates": [
            {
                "code": g.code,
                "passed": g.passed,
                "severity": g.severity,
                "failures": g.failures,
                "warnings": g.warnings,
            }
            for g in (record.validation_report.gates if record.validation_report else [])
        ],
        "publication_content_ready": record.publication_content_ready,
        "publication_reasons": record.publication_reasons,
        "model_calls": [c.as_dict() for c in record.model_calls],
        "verification": (
            {
                "answer_supported": record.verification.answer_supported,
                "ambiguous": record.verification.ambiguous,
                "unsupported_claims": record.verification.unsupported_claims,
                "notes": record.verification.notes,
            }
            if record.verification
            else None
        ),
        "final_reason": record.reason,
    }

    return StagingCandidateRecord(
        batch_id=record.batch_id,
        sequence_in_batch=sequence_in_batch,
        fact_id=spec.fact_id,
        outcome=record.status,
        attempt_number=record.attempt_number,
        generation_method="mcq_factory_groq_orchestrator",
        engine_version="orchestrator-v1",
        source_pdf=record.evidence_chunk.source_pdf if record.evidence_chunk else None,
        evidence_pages=[record.evidence_chunk.page_number] if record.evidence_chunk else None,
        evidence_quoted_text=record.evidence_chunk.quoted_snippet if record.evidence_chunk else None,
        provenance={"fact_id": spec.fact_id, "chunk_doc_id": record.evidence_chunk.doc_id if record.evidence_chunk else None},
        subject=spec.subject,
        class_level=spec.class_level,
        chapter=spec.chapter,
        topic=spec.topic,
        concept=spec.concept,
        concept_id=spec.taxonomy.concept_id,
        question_type="MCQ",
        difficulty=candidate.difficulty if candidate else None,
        question_text=candidate.stem if candidate else None,
        options=[{"label": o.label, "text": o.text} for o in candidate.options] if candidate else None,
        correct_answer=candidate.correct_option if candidate else None,
        explanation=candidate.explanation if candidate else None,
        stem_hash=record.validation_report.stem_hash if record.validation_report else None,
        option_stem_hash=record.validation_report.option_stem_hash if record.validation_report else None,
        rejection_reason=None if record.status == STATUS_ACCEPTED else record.reason[:80],
        rejection_details={"reason": record.reason},
        validation_status=record.validation_report.classification if record.validation_report else None,
        validation_result=validation_result,
        is_duplicate=is_duplicate_flag,
        duplicate_matched_source_file=duplicate_matched_source,
        duplicate_similarity=duplicate_similarity_value,
        candidate_kind="GENERATED_PRACTICE",
        evidence_relocation_confirmed=(
            any(g.code == "P_PROVENANCE" and g.passed for g in record.validation_report.gates)
            if record.validation_report
            else None
        ),
        raw_candidate={
            "candidate": body,
            # NEET-MCQ-FACTORY-5000-DELIVERY-001: the four schema-readiness
            # additions on GeneratedMcqCandidate (schemas.py) are carried here
            # in the flexible raw_candidate JSON blob rather than requiring a
            # new staging-table column/migration. All default to None/the
            # single-format default until a future prompt revision actually
            # asks the model for them — never fabricated here.
            "schema_readiness_fields": (
                {
                    "difficulty_rationale": candidate.difficulty_rationale,
                    "distractor_rationale": candidate.distractor_rationale,
                    "question_format": candidate.question_format,
                    "learning_objective": candidate.learning_objective,
                }
                if candidate
                else None
            ),
            "source_evidence": (
                {
                    "doc_id": candidate.source_evidence.doc_id,
                    "page": candidate.source_evidence.page,
                    "quoted_snippet": candidate.source_evidence.quoted_snippet,
                }
                if candidate
                else None
            ),
            "taxonomy": (
                {
                    "subject_id": candidate.taxonomy.subject_id,
                    "chapter_id": candidate.taxonomy.chapter_id,
                    "topic_id": candidate.taxonomy.topic_id,
                    "concept_id": candidate.taxonomy.concept_id,
                }
                if candidate
                else None
            ),
            "model_calls": [c.as_dict() for c in record.model_calls],
            "final_status": record.status,
            "final_reason": record.reason,
            # NEET-MCQ-FACTORY-MULTI-ATTEMPT-001: deterministic angle used
            # for this attempt's generation prompt (see
            # prompt_templates.angle_for_attempt) — GUIDANCE ONLY, never
            # proof of uniqueness; carried here purely for the batch
            # report's per-fact "angles_used" breakdown.
            "angle_name": record.angle_name,
        },
    )


# ---------------------------------------------------------------------------
# Production wiring — adapts the existing façades to the LlmCaller shape.
# Not exercised by unit tests (which inject trivial fakes directly); kept
# here so the orchestrator never has to know about AIGateway/session
# plumbing, and so this is the ONE place generation/verification callers
# are constructed for a real run.
# ---------------------------------------------------------------------------


def build_groq_generation_caller(session: Any, *, settings: Any = None) -> GenerationCaller:
    from app.modules.cms.services.mcq_llm_provider import build_mcq_llm_provider

    mcq_provider = build_mcq_llm_provider(session, settings=settings)

    async def _caller(*, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse:
        return await mcq_provider.generate_mcq(
            system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens
        )

    return _caller


def build_groq_verification_caller(session: Any, *, settings: Any = None) -> VerificationCaller | None:
    from app.modules.cms.services.mcq_llm_provider import build_mcq_verification_provider

    verification_provider = build_mcq_verification_provider(session, settings=settings)
    if verification_provider is None:
        return None

    async def _caller(*, system_prompt: str, user_prompt: str, max_tokens: int) -> AIResponse:
        return await verification_provider.verify_candidate(
            system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens
        )

    return _caller


def build_mcq_factory_generation_caller(session: Any, *, settings: Any = None) -> GenerationCaller:
    """MCQ-FACTORY-PROVIDER-AGNOSTIC-001 — generalized alternative to
    ``build_groq_generation_caller`` above (which stays untouched for
    existing callers). Resolves the generation provider+model
    independently via ``settings.mcq_factory_generation_provider`` /
    ``_model`` (defaulting to Groq's existing models when unset) instead
    of being hard-wired to the Groq-only construction path. See
    ``mcq_llm_provider.build_mcq_factory_stage_caller`` for the actual
    resolution/construction logic — this is a one-line adapter to this
    module's ``GenerationCaller`` shape, exactly like
    ``build_groq_generation_caller`` already is."""
    from app.modules.cms.services.mcq_llm_provider import build_mcq_factory_stage_caller

    return build_mcq_factory_stage_caller(session, stage="generation", settings=settings)


def build_mcq_factory_verification_caller(session: Any, *, settings: Any = None) -> VerificationCaller | None:
    """Generalized alternative to ``build_groq_verification_caller``
    above (which stays untouched for existing callers). Resolves the
    verification provider+model independently via
    ``settings.mcq_factory_verification_provider`` / ``_model``
    (defaulting to Groq's existing verification model when unset).
    Returns ``None`` exactly like ``build_groq_verification_caller`` does
    when the resolved provider is disabled/unconfigured — the
    orchestrator's never-overridable routing rule already treats a
    ``None`` verification_caller as "insufficient" (REVIEW_REQUIRED),
    never implicit agreement."""
    from app.modules.cms.services.mcq_llm_provider import build_mcq_factory_stage_caller

    return build_mcq_factory_stage_caller(session, stage="verification", settings=settings)


__all__ = [
    "STATUS_ACCEPTED",
    "STATUS_REJECTED",
    "STATUS_REVIEW_REQUIRED",
    "REASON_SKIPPED_PRIOR_ATTEMPT_REJECTED",
    "CandidateParseError",
    "LlmCaller",
    "GenerationCaller",
    "VerificationCaller",
    "StagingWriter",
    "CrossBatchDuplicateMatch",
    "CrossBatchDuplicateLookup",
    "FactSpec",
    "ModelCallAudit",
    "CandidateAuditRecord",
    "GroqFactoryOrchestrator",
    "build_groq_generation_caller",
    "build_groq_verification_caller",
    "build_mcq_factory_generation_caller",
    "build_mcq_factory_verification_caller",
]
