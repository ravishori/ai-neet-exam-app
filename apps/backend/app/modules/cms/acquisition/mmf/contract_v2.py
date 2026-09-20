"""Generation Contract V2 — declared metadata is never authoritative.

Prompt and schema versioning for post-POC hardening.
Does not mutate existing BIO11-CH04-MMF-POC-B001 artifacts.
"""

from __future__ import annotations

from typing import Any

PROMPT_VERSION_V1 = "mmf-live-poc-prompt-v1"
PROMPT_VERSION_V2 = "mmf-live-prompt-v2"
CONTRACT_VERSION = "mmf_generation_contract_v2"
CANDIDATE_SCHEMA_VERSION_V2 = "mmf_candidate_v2"

# Hard allocation caps (authoritative)
PROVIDER_CAPS: dict[str, int] = {"gemini": 400, "anthropic": 400, "openai": 200}
TOTAL_CAP = 1000

AUDITED_QUESTION_TYPES = frozenset(
    {
        "FACTUAL",
        "CONCEPTUAL",
        "DIRECT",
        "STATEMENT_BASED",
        "COMPARISON",
        "APPLICATION",
        "MULTI_STATEMENT",
    }
)

DECLARED_DIFFICULTIES = frozenset({"easy", "medium", "hard"})
AUDITED_DIFFICULTIES = frozenset({"EASY", "MEDIUM", "HARD", "UNCERTAIN"})

SYSTEM_PROMPT_V2 = """You are an NCERT-grounded NEET MCQ author for Class 11 Biology Chapter 4 Animal Kingdom.

Generate questions ONLY from the supplied NCERT excerpt. Do not use external facts.
Do not fabricate page numbers or citations.

Return ONLY a JSON object (no markdown fences) of the form:
{"questions":[ ... ]}

Each question object MUST have:
- stem
- options {A,B,C,D} — exactly four DISTINCT plausible distractors; no duplicates
- correct_answer (exactly one of A|B|C|D)
- explanation — supports the correct answer; does not merely restate the letter
- source_evidence — verbatim or near-verbatim from the supplied excerpt
- topic
- concept — prefer an approved concept CODE when confident; otherwise leave concept unresolved via concept_status
- concept_status — RESOLVED | UNRESOLVED
- question_type — one of: FACTUAL, CONCEPTUAL, DIRECT, STATEMENT_BASED, COMPARISON, APPLICATION, MULTI_STATEMENT
- difficulty — easy | medium | hard
- question_pattern — same family as question_type

CRITICAL METADATA RULE:
The declared question_type and difficulty are metadata SUGGESTIONS only.
They will be independently audited by validators and must NOT be treated as authoritative truth.
Do not inflate difficulty artificially.

Hard rules:
- use ONLY the supplied NCERT source
- exactly four options; exactly one correct answer
- no answer leakage in the stem
- no duplicate options
- one primary concept per question where appropriate
- no ContentItem / ECAEP / publish semantics in the payload
"""


def build_user_prompt_v2(
    *,
    slots: list[dict[str, Any]],
    excerpt: str,
    approved_concept_codes: list[str],
) -> str:
    import json

    payload = {
        "contract_version": CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION_V2,
        "task": f"Generate exactly {len(slots)} distinct NEET MCQs from the NCERT excerpt.",
        "response_shape": {"questions": ["<question objects>"]},
        "constraints": {
            "grounding": "NCERT excerpt only",
            "no_page_numbers": True,
            "no_external_facts": True,
            "options": "exactly A-D, distinct, plausible",
            "one_correct_answer": True,
            "approved_concept_codes": approved_concept_codes,
            "concept_policy": "Prefer approved codes; if unsure set concept_status=UNRESOLVED — do not invent taxonomy",
            "declared_metadata_note": (
                "declared question_type and difficulty are suggestions and will be independently audited"
            ),
            "no_artificial_difficulty": True,
            "diversity": "do not paraphrase the same fact across items",
        },
        "slots": slots,
        "ncert_excerpt": excerpt,
    }
    return json.dumps(payload, ensure_ascii=False)


def contract_v2_document() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "prompt_version": PROMPT_VERSION_V2,
        "previous_prompt_version": PROMPT_VERSION_V1,
        "schema_versions": {
            "candidate_v1": "mmf_candidate_v1",
            "candidate_v2": CANDIDATE_SCHEMA_VERSION_V2,
        },
        "metadata_policy": {
            "declared_fields": ["question_type", "difficulty", "declared_question_type", "declared_difficulty"],
            "audited_fields": ["audited_question_type", "audited_difficulty"],
            "authority": "AUDITED fields are measurement; DECLARED fields are generator suggestions only",
            "no_silent_rewrite_of_declared": True,
        },
        "allocation_caps": {**PROVIDER_CAPS, "total": TOTAL_CAP},
        "audited_question_types": sorted(AUDITED_QUESTION_TYPES),
        "audited_difficulties": sorted(AUDITED_DIFFICULTIES),
        "concept_policy": {
            "prefer_approved_codes": True,
            "unresolved_status": "UNRESOLVED",
            "auto_create_taxonomy": False,
        },
        "ncert_grounding": {
            "required": ["source_document", "source_sha256", "source_evidence", "generation_batch_id", "provider", "model", "prompt_version"],
            "no_fabricated_page_numbers": True,
            "no_silent_upgrade_weak_to_direct": True,
        },
        "system_prompt_v2": SYSTEM_PROMPT_V2,
        "poc_artifacts_immutable": True,
        "live_generation_this_gate": False,
    }


__all__ = [
    "AUDITED_DIFFICULTIES",
    "AUDITED_QUESTION_TYPES",
    "CANDIDATE_SCHEMA_VERSION_V2",
    "CONTRACT_VERSION",
    "DECLARED_DIFFICULTIES",
    "PROMPT_VERSION_V1",
    "PROMPT_VERSION_V2",
    "PROVIDER_CAPS",
    "SYSTEM_PROMPT_V2",
    "TOTAL_CAP",
    "build_user_prompt_v2",
    "contract_v2_document",
]
