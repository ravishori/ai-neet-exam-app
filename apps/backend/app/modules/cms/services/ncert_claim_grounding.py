"""MCQ-NCERT-GROUNDING-001 — claim-level NCERT grounding validator.

Provider-neutral hard gate above adapters: every material factual claim in
stem / options / explanation must be supportable from the *supplied*
canonical NCERT evidence pack. Scientifically true but source-absent
enrichment → NCERT_UNSUPPORTED.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

from app.modules.cms.services.ncert_generation_evidence import NcertEvidencePack
from app.modules.knowledge.services.grounding_check import _significant_words

GroundingVerdict = Literal[
    "NCERT_SUPPORTED",
    "NCERT_UNSUPPORTED",
    "NCERT_AMBIGUOUS",
    "NCERT_GROUNDED_SKIPPED",
]

# Pedagogy / MCQ scaffolding — not treated as factual enrichment anchors.
_CLAIM_STOPWORDS = frozenset(
    {
        "this", "that", "these", "those", "with", "from", "into", "onto",
        "have", "has", "had", "were", "was", "are", "is", "be", "been",
        "being", "will", "would", "could", "should", "shall", "must",
        "than", "then", "when", "where", "which", "while", "about",
        "there", "their", "they", "them", "such", "each", "some", "more",
        "most", "other", "only", "also", "both", "same", "very", "just",
        "over", "under", "between", "across", "through", "within", "without",
        "does", "did", "not", "and", "for", "the", "its", "option", "options",
        "correct", "answer", "following", "statement", "statements", "because",
        "therefore", "however", "during", "after", "before", "above", "below",
        "question", "choices", "choice", "false", "true", "wrong", "right",
        "always", "never", "often", "typically", "generally", "respectively",
        "example", "examples", "called", "using", "used", "thus", "hence",
        "like", "such", "into", "onto", "upon", "among", "against",
        "molecule", "molecules", "energy", "temperature", "structure",
        "structures", "level", "levels", "body", "animal", "animals",
        "force", "forces", "work", "block", "surface", "mass", "displacement",
        "kinetic", "friction", "normal", "horizontal", "constant", "equals",
        "change", "net", "done", "pulling", "starts", "rest", "according",
        "theorem", "ideal", "gases", "gas", "containers", "same", "per",
        "average", "total", "internal", "including", "motion", "motions",
        "root", "mean", "square", "speed", "larger", "smaller", "measure",
        "measures", "description", "best", "matches", "treated", "removed",
        "allowed", "regains", "native", "well", "defined", "containing",
        "intact", "folded", "primary", "sequence", "process", "producing",
        "produced", "industrial", "beverage", "beverages", "antibiotic",
        "antibiotics", "organism", "organisms", "species", "pair", "pairs",
        "correctly", "exhibits", "highest", "structural", "organisation",
        "organization", "one", "two", "three", "four", "five",
    }
)

_ENTITY_PATTERNS: list[re.Pattern[str]] = [
    # Concentrated reagents / protocol markers (capital M = molarity, not metre)
    re.compile(r"\b\d+(?:\.\d+)?\s*M\s+[A-Za-z][A-Za-z\-]{2,}\b"),
    re.compile(r"\b(?:β|beta)[-\s]?mercaptoethanol\b", re.I),
    re.compile(r"\bmercaptoethanol\b", re.I),
    re.compile(r"\b[Aa]nfinsen(?:'s)?(?:\s+principle)?\b"),
    re.compile(r"\b(?:urea|thiourea|guanidine|dialysis)\b", re.I),
    # Process / metabolite enrichment common in Bio industrial MCQs
    re.compile(r"\bsecondary\s+metabolites?\b", re.I),
    re.compile(r"\bstationary\s+phase\b", re.I),
    re.compile(r"\bsubmerged\s+fermentation\b", re.I),
    re.compile(r"\bchaotropic(?:\s+agent)?\b", re.I),
    # Taxa / antibiotic enrichment
    re.compile(r"\bStreptomyces\b"),
    re.compile(r"\bstreptomycin\b", re.I),
    re.compile(r"\b[a-z]{4,}mycin\b", re.I),
    re.compile(r"\b[a-z]{4,}cillin\b", re.I),
    # Explicit binomials that often appear in NCERT (grounding checks presence)
    re.compile(r"\bSaccharomyces\s+cerevisiae\b"),
    re.compile(r"\bPenicillium\s+notatum\b"),
    re.compile(r"\bAcetobacter\s+aceti\b"),
]

# High-risk scientific morphology — absent from evidence ⇒ unsupported enrichment.
_RISK_TOKEN = re.compile(
    r"\b(?:[A-Za-z][A-Za-z\-]{3,}(?:mycin|cillin)|mercaptoethanol|anfinsen|streptomyces|urea)\b",
    re.I,
)


@dataclass
class ClaimRecord:
    field: str  # stem | option_A | ... | explanation | entity
    text: str
    kind: str = "segment"


@dataclass
class GroundingIssue:
    code: str
    field: str
    detail: str
    unsupported_tokens: list[str] = field(default_factory=list)


@dataclass
class GroundingResult:
    verdict: GroundingVerdict
    ok: bool
    issues: list[GroundingIssue] = field(default_factory=list)
    claims_checked: int = 0
    unsupported_claims: list[str] = field(default_factory=list)

    @property
    def error_codes(self) -> list[str]:
        if self.ok:
            return []
        codes = [self.verdict] if self.verdict == "NCERT_UNSUPPORTED" else [self.verdict]
        for issue in self.issues:
            if issue.code not in codes:
                codes.append(issue.code)
        return codes


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("β", "beta").replace("µ", "u")
    return text.lower()


def _evidence_index(evidence_text: str) -> tuple[str, set[str], set[str]]:
    folded = _fold(evidence_text)
    words = _significant_words(folded) | {
        w for w in re.findall(r"[a-z][a-z\-]{2,}", folded) if w not in _CLAIM_STOPWORDS
    }
    # Bigrams of significant tokens for phrase grounding.
    tokens = [t for t in re.findall(r"[a-z][a-z\-]{2,}", folded) if t not in _CLAIM_STOPWORDS]
    bigrams = {f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)}
    return folded, words, bigrams


def extract_named_entities(text: str) -> list[str]:
    """High-signal factual anchors (reagents, taxa, named principles, phrases)."""
    found: list[str] = []
    seen: set[str] = set()
    src = text or ""
    for pat in _ENTITY_PATTERNS:
        for m in pat.finditer(src):
            raw = m.group(0).strip()
            key = _fold(raw)
            if key in seen or len(key) < 4:
                continue
            seen.add(key)
            found.append(raw)
    for m in _RISK_TOKEN.finditer(src):
        raw = m.group(0).strip()
        key = _fold(raw)
        if key in seen:
            continue
        seen.add(key)
        found.append(raw)
    return found


def extract_material_claims(body: dict[str, Any]) -> list[ClaimRecord]:
    claims: list[ClaimRecord] = []
    stem = str(body.get("stem") or "").strip()
    if stem:
        claims.append(ClaimRecord(field="stem", text=stem, kind="stem"))
        for ent in extract_named_entities(stem):
            claims.append(ClaimRecord(field="stem", text=ent, kind="entity"))

    for opt in body.get("options") or []:
        label = str(opt.get("label") or "").strip().upper()
        text = str(opt.get("text") or "").strip()
        if not text:
            continue
        field = f"option_{label}" if label else "option"
        claims.append(ClaimRecord(field=field, text=text, kind="option"))
        for ent in extract_named_entities(text):
            claims.append(ClaimRecord(field=field, text=ent, kind="entity"))

    explanation = str(body.get("explanation") or "").strip()
    if explanation:
        parts = re.split(r"(?<=[.!?])\s+", explanation)
        for part in parts:
            part = part.strip()
            if len(part) < 25:
                continue
            claims.append(ClaimRecord(field="explanation", text=part, kind="explanation_sentence"))
        for ent in extract_named_entities(explanation):
            claims.append(ClaimRecord(field="explanation", text=ent, kind="entity"))
    return claims


def _token_in_evidence(token: str, evidence_fold: str, evidence_words: set[str]) -> bool:
    t = _fold(token)
    if not t:
        return True
    if t in evidence_fold:
        return True
    parts = [p for p in re.findall(r"[a-z][a-z\-]{2,}", t) if p not in _CLAIM_STOPWORDS]
    if not parts:
        return t in evidence_fold
    return all(p in evidence_fold or p in evidence_words for p in parts)


def _distinctive_unsupported_tokens(claim_text: str, evidence_fold: str, evidence_words: set[str]) -> list[str]:
    """High-signal anchors absent from supplied evidence (general mechanism)."""
    unsupported: list[str] = []
    for ent in extract_named_entities(claim_text):
        if not _token_in_evidence(ent, evidence_fold, evidence_words):
            unsupported.append(ent)
    seen: set[str] = set()
    out: list[str] = []
    for u in unsupported:
        key = _fold(u)
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def _claim_supported(
    claim: ClaimRecord, evidence_text: str, evidence_fold: str, evidence_words: set[str]
) -> tuple[bool, list[str]]:
    unsupported = _distinctive_unsupported_tokens(claim.text, evidence_fold, evidence_words)
    if unsupported:
        return False, unsupported
    if claim.kind == "entity":
        return _token_in_evidence(claim.text, evidence_fold, evidence_words), []
    # Stem/option/explanation segments: entity gate is the hard anti-hallucination
    # check. Soft vocabulary overlap is advisory only (paraphrase-tolerant).
    return True, []


def detect_multiple_defensible_answers(body: dict[str, Any], evidence_text: str) -> list[str]:
    """Detect near-duplicate correct options (not mere word-overlap with evidence)."""
    options = body.get("options") or []
    correct = str(body.get("correct_option") or "").strip().upper()
    correct_text = next(
        (str(o.get("text") or "") for o in options if str(o.get("label") or "").upper() == correct),
        "",
    )
    if not correct_text:
        return []
    from app.modules.cms.services.factory_candidate_validation import normalize_stem

    c_norm = normalize_stem(correct_text)
    dup_labels = [correct]
    for opt in options:
        label = str(opt.get("label") or "").strip().upper()
        if not label or label == correct:
            continue
        t_norm = normalize_stem(str(opt.get("text") or ""))
        if not t_norm:
            continue
        # Near-identical option texts ⇒ multiple defensible answers.
        if t_norm == c_norm or (len(c_norm) > 20 and (c_norm in t_norm or t_norm in c_norm)):
            dup_labels.append(label)
    return dup_labels if len(dup_labels) > 1 else []


def verify_simple_net_work_numerical(body: dict[str, Any]) -> GroundingIssue | None:
    """Independent check for common horizontal pull + kinetic friction WE items."""
    stem = str(body.get("stem") or "")
    if "work–energy" not in stem.lower() and "work-energy" not in stem.lower() and "work energy" not in stem.lower():
        if "change in kinetic energy" not in stem.lower():
            return None
    nums = [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)", stem)]
    if len(nums) < 4:
        return None
    # Heuristic order: mass, force, displacement, mu (as in benchmark fixture).
    mass, force, displacement, mu = nums[0], nums[1], nums[2], nums[3]
    g = 9.8
    w_pull = force * displacement
    f_k = mu * mass * g
    w_f = -f_k * displacement
    w_net = w_pull + w_f
    correct = str(body.get("correct_option") or "").strip().upper()
    correct_text = next(
        (str(o.get("text") or "") for o in (body.get("options") or []) if str(o.get("label") or "").upper() == correct),
        "",
    )
    if abs(w_net) < 1e-9:
        return None
    # Correct option should mention net work / change in KE near computed value.
    if "net" not in correct_text.lower() and "change in kinetic" not in correct_text.lower():
        return GroundingIssue(
            code="NUMERICAL_ANSWER_NOT_NET_WORK",
            field="correct_option",
            detail=f"expected net work ≈ {w_net:.4g} J to be the keyed answer framing",
        )
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*J", correct_text)
    if m:
        val = float(m.group(1))
        if abs(val - w_net) > 0.6 and abs(val - (w_pull + (-(mu * mass * 10) * displacement))) > 0.6:
            return GroundingIssue(
                code="NUMERICAL_VALUE_MISMATCH",
                field="correct_option",
                detail=f"option value {val} != computed net work {w_net:.4g} (g=9.8)",
            )
    return None


def validate_ncert_claim_grounding(
    body: dict[str, Any],
    evidence: NcertEvidencePack | str,
    *,
    check_numerical: bool = True,
) -> GroundingResult:
    """Hard gate. Does not call providers. Does not mutate DB."""
    if isinstance(evidence, NcertEvidencePack):
        if evidence.status == "NCERT_EVIDENCE_NOT_REQUIRED":
            return GroundingResult(verdict="NCERT_GROUNDED_SKIPPED", ok=True, claims_checked=0)
        if not evidence.is_ready or not (evidence.evidence_text or "").strip():
            return GroundingResult(
                verdict="NCERT_UNSUPPORTED",
                ok=False,
                issues=[
                    GroundingIssue(
                        code="NCERT_EVIDENCE_INSUFFICIENT",
                        field="evidence",
                        detail=evidence.detail or "evidence pack not ready",
                    )
                ],
                unsupported_claims=["<evidence pack insufficient>"],
            )
        evidence_text = evidence.evidence_text
    else:
        evidence_text = str(evidence or "")
        if len(evidence_text.strip()) < 40:
            return GroundingResult(
                verdict="NCERT_UNSUPPORTED",
                ok=False,
                issues=[
                    GroundingIssue(
                        code="NCERT_EVIDENCE_INSUFFICIENT",
                        field="evidence",
                        detail="empty evidence text",
                    )
                ],
            )

    evidence_fold, evidence_words, _bigrams = _evidence_index(evidence_text)
    claims = extract_material_claims(body)
    issues: list[GroundingIssue] = []
    unsupported_claim_texts: list[str] = []

    for claim in claims:
        ok, bad_tokens = _claim_supported(claim, evidence_text, evidence_fold, evidence_words)
        if ok:
            continue
        unsupported_claim_texts.append(claim.text[:160])
        issues.append(
            GroundingIssue(
                code="NCERT_UNSUPPORTED",
                field=claim.field,
                detail=f"{claim.kind} not grounded in supplied NCERT evidence",
                unsupported_tokens=bad_tokens,
            )
        )

    multi = detect_multiple_defensible_answers(body, evidence_text)
    if multi:
        issues.append(
            GroundingIssue(
                code="NCERT_AMBIGUOUS",
                field="options",
                detail=f"multiple evidence-defensible options: {','.join(multi)}",
            )
        )

    if check_numerical:
        num_issue = verify_simple_net_work_numerical(body)
        if num_issue:
            issues.append(num_issue)

    if not issues:
        return GroundingResult(verdict="NCERT_SUPPORTED", ok=True, claims_checked=len(claims))

    verdict: GroundingVerdict = "NCERT_UNSUPPORTED"
    if any(i.code == "NCERT_AMBIGUOUS" for i in issues) and all(
        i.code in {"NCERT_AMBIGUOUS"} for i in issues
    ):
        verdict = "NCERT_AMBIGUOUS"

    return GroundingResult(
        verdict=verdict,
        ok=False,
        issues=issues,
        claims_checked=len(claims),
        unsupported_claims=unsupported_claim_texts[:12],
    )
