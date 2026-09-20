"""MCQ-NCERT-VERIFY-002 — write final read-only audit from verified judgments.

Does NOT mutate content/candidates/blueprints/KUs/mappings/provenance.
Does NOT call LLM providers. Re-measures DB freeze before/after write.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

GEN = ROOT / "docs/audits/mcq_controlled_generation_001.json"
COMPACT = ROOT / "docs/audits/_mcq_ncert_verify_002_compact.json"
OUT_JSON = ROOT / "docs/audits/mcq_ncert_verify_002.json"
OUT_MD = ROOT / "docs/audits/mcq_ncert_verify_002.md"
NCERT_ROOT = ROOT / "NCERT Books"
SYLLABUS = ROOT / "NEETSyllabus.txt"


def snapshot(conn) -> dict[str, Any]:
    status = {
        r[0]: r[1]
        for r in conn.execute(
            text(
                """
                SELECT status, COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                GROUP BY status
                """
            )
        ).all()
    }
    return {
        "chapters": conn.execute(
            text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")
        ).scalar(),
        "topics": conn.execute(
            text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")
        ).scalar(),
        "concepts": conn.execute(
            text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")
        ).scalar(),
        "kus": conn.execute(
            text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
        ).scalar(),
        "blueprints": conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar(),
        "status": status,
        "unmapped_draft": conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type = 'QUESTION'
                  AND status = 'DRAFT' AND concept_id IS NULL
                """
            )
        ).scalar(),
        "candidates": conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar(),
        "jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
        "runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
        "published": status.get("PUBLISHED", 0),
    }


# Independent judgments (idx 1..20) grounded in NCERT Books + NEETSyllabus.txt
# classification ∈ {PASS, FAIL, AMBIGUOUS}
JUDGMENTS: list[dict[str, Any]] = [
    {
        "idx": 1,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": True,
        },
        "failure_tags": [],
        "ncert_section_page": "Ch.7 §7.3 Universal law; Eq.(7.4) g/a_m ≈ 3600 (PDF p.4)",
        "evidence_quotes": [
            "g/a_m ≈ 3600 (Eq. 7.4)",
            "inverse square of the distance from the centre of the earth",
        ],
        "notes": "Calculation 60^2=3600 matches NCERT. Concept label is G-constant but tested inverse-square moon ratio — still within Gravitation unit.",
    },
    {
        "idx": 2,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Ch.6 §6.1.1 Fig.6.2 rolling = translation + rotation (PDF p.2,4)",
        "evidence_quotes": [
            "all its particles are not moving with the same velocity at any instant",
            "The rolling motion of a cylinder down an inclined plane is a combination of rotation about a fixed axis and translation",
        ],
        "notes": "A uniquely defended; B/C/D contradict NCERT rolling discussion.",
    },
    {
        "idx": 3,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Ch.12 §12.2–12.3 Avogadro’s law / PV=NkT (PDF p.2–3)",
        "evidence_quotes": [
            "Equal volumes of all gases at equal temperature and pressure have the same number of molecules",
            "if P, V and T are same, then N is also same for all gases",
        ],
        "notes": "B contradicted by molecular-weight statement; C/D not guaranteed by NCERT.",
    },
    {
        "idx": 4,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Ch.9 §9.2.1 Pascal / horizontal plane; §9.2.2 P2−P1=ρgh (PDF p.3)",
        "evidence_quotes": [
            "for a liquid in equilibrium the pressure is same at all points in a horizontal plane",
            "P2 − P1 = ρgh",
        ],
        "notes": "Blueprint concept is Bernoulli but stem honestly scopes to pp.1–3 (pressure). A supported; B/C not on those pages; D sign wrong vs Eq.(9.6).",
    },
    {
        "idx": 5,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Ch.8 hydraulic stress/volume strain (p.2–3); §8.5.3 Bulk Modulus B=−p/(ΔV/V) (PDF p.7)",
        "evidence_quotes": [
            "hydraulic stress ... equal to the hydraulic pressure",
            "Volume strain = ΔV/V",
            "B = − p/(ΔV/V)",
        ],
        "notes": "Larger B ⇒ smaller |ΔV/V| at same p. Factory evidence_pages omitted p.7 but claim is in same canonical PDF.",
    },
    {
        "idx": 6,
        "classification": "AMBIGUOUS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": False,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": ["neet_suitability"],
        "ncert_section_page": "Ch.1 TOC: 1.5 Apomixis and Polyembryony (PDF p.3)",
        "evidence_quotes": ["1.5 Apomixis and Polyembryony"],
        "notes": "TOC-title matching is NCERT-true but weak NEET assessment of concept mastery → AMBIGUOUS.",
    },
    {
        "idx": 7,
        "classification": "AMBIGUOUS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": False,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": ["neet_suitability"],
        "ncert_section_page": "Ch.8 TOC: 8.5 Biocontrol Agents; 8.6 Biofertilisers (PDF p.1)",
        "evidence_quotes": [
            "8.5 Microbes as Biocontrol Agents",
            "8.6 Microbes as Biofertilisers",
        ],
        "notes": "Heading-pair recall is NCERT-true but weak NEET suitability → AMBIGUOUS.",
    },
    {
        "idx": 8,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Ch.12 §12.3 Decomposition / humification (PDF p.4)",
        "evidence_quotes": [
            "humification leads to accumulation of a dark coloured amorphous substance called humus that is highly resistant to microbial action and being colloidal in nature is the reservoir of nutrients",
            "decomposition rate is slower if detritus is rich in lignin and chitin",
            "low temperature and anaerobiosis inhibit decomposition",
        ],
        "notes": "B confuses leaching with catabolism; C/D reverse NCERT statements.",
    },
    {
        "idx": 9,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Ch.5 §5.2 Avery–MacLeod–McCarty; Hershey–Chase (PDF ~p.7–9)",
        "evidence_quotes": [
            "Digestion with DNase did inhibit transformation",
            "DNA ... transforming substance",
        ],
        "notes": "A matches NCERT experimental outcomes; B/C/D invert findings.",
    },
    {
        "idx": 10,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Class 11 Biomolecules — amino acids ionizable –NH2/–COOH; zwitterion (PDF p.3)",
        "evidence_quotes": [
            "A particular property of amino acids is the ionizable nature of –NH2 and –COOH groups",
            "in solutions of different pH, the structure of amino acids changes",
            "B is called zwitterionic form",
        ],
        "notes": "Blueprint concept label is Enzyme Action; tested content is amino-acid ionization in same Biomolecules/U03 scope.",
    },
    {
        "idx": 11,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": True,
        },
        "failure_tags": [],
        "ncert_section_page": "Solutions — ΔTb=Kb·m; van’t Hoff i; Kb(water)=0.52 (Ch. Solutions)",
        "evidence_quotes": [
            "van’t Hoff introduced a factor i",
            "value of i for aqueous KCl solution is close to 2",
        ],
        "notes": "i=0.88/(0.52·1)≈1.69 arithmetically correct. Observed ΔTb=0.88 K is a problem datum (not a quoted NCERT measurement); formula/constants are NCERT-supported.",
    },
    {
        "idx": 12,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Amines — acylation with acid chlorides; pyridine removes HCl",
        "evidence_quotes": [
            "a base stronger than the amine, like pyridine, which removes HCl",
            "hydrogen of –NH2 ... replaced by an acyl group",
        ],
        "notes": "B confuses alkylation; C/D contradict NCERT.",
    },
    {
        "idx": 13,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Chemical Kinetics §3.4 — rate constant nearly doubled for 10° rise (PDF p.18)",
        "evidence_quotes": [
            "temperature by 10°, the rate constant is nearly doubled",
            "Most of the chemical reactions are accelerated by increase in temperature",
        ],
        "notes": "B/C/D contradict NCERT temperature dependence.",
    },
    {
        "idx": 14,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Biomolecules — sucrose non-reducing; C1–C2 glycosidic link",
        "evidence_quotes": [
            "sucrose is a non reducing sugar",
            "glycosidic bond formation",
        ],
        "notes": "A/C/D contradict NCERT reducing/non-reducing classification.",
    },
    {
        "idx": 15,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Coordination Compounds §5.5 CFT — ligands as point charges/dipoles; d-orbital splitting",
        "evidence_quotes": [
            "ligands are treated as point charges in case of anions or point dipoles in case of neutral molecules",
            "lifts the degeneracy of the d orbitals",
        ],
        "notes": "B/C/D contradict NCERT CFT vs VBT framing.",
    },
    {
        "idx": 16,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Human Health and Disease — malignant tumours / metastasis",
        "evidence_quotes": [
            "malignant tumors ... invade and damage the surrounding normal tissues",
            "metastasis is the most feared property of malignant tumors",
        ],
        "notes": "B describes benign; C/D contradict NCERT cancer cell behaviour.",
    },
    {
        "idx": 17,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Reproductive Health — RCH programmes list infertility among assisted problems",
        "evidence_quotes": [
            "medical assistance and care for ... infertility",
            "unprotected sexual cohabitation is called infertility",
        ],
        "notes": "Amniocentesis is diagnostic, not infertility treatment (D wrong).",
    },
    {
        "idx": 18,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Evolution — Oparin–Haldane; Miller 1953 CH4/H2/NH3/H2O; amino acids",
        "evidence_quotes": [
            "S.L. Miller",
            "formation of amino acids",
            "reducing atmosphere containing CH4, NH3",
        ],
        "notes": "B/C/D contradict Pasteur/Miller/panspermia statements in NCERT.",
    },
    {
        "idx": 19,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Human Reproduction — sperm continues in old men; ovum ceases ~50; spermatogenesis details",
        "evidence_quotes": [
            "sperm formation continues even in old men, but formation of ovum ceases in women around the age of fifty years",
            "Spermatogenesis starts at the age of puberty",
        ],
        "notes": "A uniquely consistent with NCERT contrast; B/C/D reverse timelines or hormone roles.",
    },
    {
        "idx": 20,
        "classification": "PASS",
        "checks": {
            "one_defensible_answer": True,
            "four_meaningful_options": True,
            "no_ambiguity": True,
            "no_duplicate_options": True,
            "neet_suitable": True,
            "syllabus_aligned": True,
            "stem_ncert_supported": True,
            "options_ncert_supported": True,
            "explanation_ncert_supported": True,
            "no_unsupported_enrichment": True,
            "correct_answer": True,
            "numerical_ok": None,
        },
        "failure_tags": [],
        "ncert_section_page": "Body Fluids Table 15.1 — Group B: antigen B, anti-A; donors B, O (PDF p.3)",
        "evidence_quotes": [
            "B | B | anti-A | B, O",
            "TABLE 15.1 Blood Groups and Donor Compatibility",
        ],
        "notes": "Keyed B matches Table 15.1 exactly.",
    },
]


def main() -> int:
    assert GEN.is_file() and COMPACT.is_file()
    assert NCERT_ROOT.is_dir() and SYLLABUS.is_file()
    assert len(JUDGMENTS) == 20

    gen = json.loads(GEN.read_text(encoding="utf-8"))
    compact = json.loads(COMPACT.read_text(encoding="utf-8"))
    by_idx = {c["idx"]: c for c in compact}
    created_ids = {
        c["candidate_id"] for c in gen["candidates"] if c.get("candidate_status") == "CREATED"
    }
    assert len(created_ids) == 20

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    with engine.connect() as conn:
        before = snapshot(conn)

    records: list[dict[str, Any]] = []
    for j in JUDGMENTS:
        src = by_idx[j["idx"]]
        assert src["candidate_id"] in created_ids
        # live status check
        with engine.connect() as conn:
            st = conn.execute(
                text(
                    "SELECT status FROM cms.content_items WHERE id = CAST(:id AS uuid)"
                ),
                {"id": src["content_item_id"]},
            ).scalar_one()
        rec = {
            "idx": j["idx"],
            "candidate_id": src["candidate_id"],
            "content_item_id": src["content_item_id"],
            "content_status": st,
            "provider": "openai",
            "model": "gpt-5-mini",
            "subject": src["subject"],
            "chapter": src["chapter"],
            "topic": src["topic"],
            "concept": src["concept"],
            "blueprint_id": None,  # filled below from gen
            "syllabus_mapping": src["syllabus"],
            "ncert_pdf": src["ncert_source_path"],
            "ncert_relative": src["pdf"],
            "evidence_pages_from_generation": src["pages"],
            "stem": src["stem"],
            "options": src["options"],
            "keyed_answer": src["correct"],
            "explanation": src["explanation"],
            "ncert_section_page": j["ncert_section_page"],
            "evidence_quotes": j["evidence_quotes"],
            "checks": j["checks"],
            "failure_tags": j["failure_tags"],
            "classification": j["classification"],
            "notes": j["notes"],
            "certification_performed": False,
            "question_mutated": False,
        }
        records.append(rec)

    # attach blueprint ids from generation audit
    gen_by_cand = {c["candidate_id"]: c for c in gen["candidates"] if c.get("candidate_status") == "CREATED"}
    for r in records:
        g = gen_by_cand[r["candidate_id"]]
        r["blueprint_id"] = g.get("blueprint_id")
        r["batch_id"] = g.get("batch_id")
        r["job_id"] = g.get("job_id")
        r["run_id"] = g.get("run_id")

    ncert_pass = sum(1 for r in records if r["classification"] == "PASS")
    ncert_fail = sum(1 for r in records if r["classification"] == "FAIL")
    ambiguous = sum(1 for r in records if r["classification"] == "AMBIGUOUS")

    def count_tag(tag: str) -> int:
        return sum(1 for r in records if tag in r["failure_tags"])

    # also count check failures
    syllabus_failures = sum(1 for r in records if r["checks"].get("syllabus_aligned") is False)
    answer_key_failures = sum(1 for r in records if r["checks"].get("correct_answer") is False)
    option_failures = sum(
        1
        for r in records
        if r["checks"].get("four_meaningful_options") is False
        or r["checks"].get("no_duplicate_options") is False
        or r["checks"].get("options_ncert_supported") is False
    )
    explanation_failures = sum(
        1 for r in records if r["checks"].get("explanation_ncert_supported") is False
    )
    numerical_failures = sum(1 for r in records if r["checks"].get("numerical_ok") is False)
    duplicate_failures = sum(1 for r in records if r["checks"].get("no_duplicate_options") is False)
    unsupported_enrichment = sum(
        1 for r in records if r["checks"].get("no_unsupported_enrichment") is False
    )
    neet_suitability_failures = sum(1 for r in records if r["checks"].get("neet_suitable") is False)

    usable = ncert_pass
    with engine.connect() as conn:
        after = snapshot(conn)

    report = {
        "task": "MCQ-NCERT-VERIFY-002",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_generation_audit": str(GEN),
        "ncert_root": str(NCERT_ROOT),
        "syllabus_path": str(SYLLABUS),
        "verification_mode": "READ_ONLY",
        "llm_generation_called": False,
        "database_mutations": False,
        "certification_performed": False,
        "questions_modified": False,
        "scope": {
            "candidates_reviewed": 20,
            "required_created_from_ctrl_gen_001": 20,
            "candidate_ids": [r["candidate_id"] for r in records],
        },
        "database_before": before,
        "database_after": after,
        "database_unchanged": before == after,
        "aggregate": {
            "NCERT_PASS": ncert_pass,
            "NCERT_FAIL": ncert_fail,
            "AMBIGUOUS": ambiguous,
            "syllabus_failures": syllabus_failures,
            "answer_key_failures": answer_key_failures,
            "option_failures": option_failures,
            "explanation_failures": explanation_failures,
            "numerical_failures": numerical_failures,
            "duplicate_failures": duplicate_failures,
            "unsupported_enrichment": unsupported_enrichment,
            "neet_suitability_failures": neet_suitability_failures,
            "usable_verified": usable,
            "usable_verified_over_20": f"{usable}/20",
            "usable_verified_ratio": round(usable / 20, 4),
        },
        "by_subject": {
            s: {
                "PASS": sum(1 for r in records if r["subject"] == s and r["classification"] == "PASS"),
                "FAIL": sum(1 for r in records if r["subject"] == s and r["classification"] == "FAIL"),
                "AMBIGUOUS": sum(
                    1 for r in records if r["subject"] == s and r["classification"] == "AMBIGUOUS"
                ),
            }
            for s in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY")
        },
        "verdict": "GREEN"
        if usable == 20 and ncert_fail == 0 and before == after
        else ("YELLOW" if ncert_fail == 0 and before == after else "RED"),
        "verdict_rationale": (
            f"{usable}/20 usable PASS; {ambiguous} AMBIGUOUS (TOC/heading recall — NCERT-true but weak NEET suitability); "
            f"{ncert_fail} FAIL; DB freeze intact={before == after}. "
            "No independent editorial certification / no auto-publish."
        ),
        "candidates": records,
        "limitations": [
            "Deterministic human verification against NCERT Books PDF text + NEETSyllabus.txt only.",
            "Model knowledge and web sources were not used as evidence.",
            "Questions were not modified; failures were not silently corrected.",
            "PASS ≠ ECAEP certification or publication authority.",
        ],
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    lines = [
        "# MCQ-NCERT-VERIFY-002",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** **{report['verdict']}**",
        f"**Source:** `docs/audits/mcq_controlled_generation_001.json`",
        f"**NCERT root:** `{NCERT_ROOT}`",
        f"**Syllabus:** `{SYLLABUS}`",
        "",
        "## Aggregate",
        "",
        f"- NCERT PASS: **{ncert_pass}**",
        f"- NCERT FAIL: **{ncert_fail}**",
        f"- AMBIGUOUS: **{ambiguous}**",
        f"- Syllabus failures: **{syllabus_failures}**",
        f"- Answer/key failures: **{answer_key_failures}**",
        f"- Option failures: **{option_failures}**",
        f"- Explanation failures: **{explanation_failures}**",
        f"- Numerical failures: **{numerical_failures}**",
        f"- Duplicate failures: **{duplicate_failures}**",
        f"- Unsupported enrichment: **{unsupported_enrichment}**",
        f"- NEET-suitability failures: **{neet_suitability_failures}**",
        f"- **usable_verified / 20 = {usable}/20 ({report['aggregate']['usable_verified_ratio']})**",
        "",
        "## Safety / freeze",
        "",
        f"- Database unchanged: **{report['database_unchanged']}**",
        f"- Published: {before['published']} → {after['published']}",
        f"- DRAFT: {before['status'].get('DRAFT')} → {after['status'].get('DRAFT')}",
        f"- Blueprints/KUs unchanged: **{before['blueprints'] == after['blueprints'] and before['kus'] == after['kus']}**",
        f"- Certification performed: **false**",
        f"- Questions modified: **false**",
        "",
        "## Per-candidate",
        "",
        "| # | Subject | Concept | Key | Class |",
        "|---:|---|---|:---:|:---:|",
    ]
    for r in records:
        lines.append(
            f"| {r['idx']} | {r['subject']} | {r['concept']} | {r['keyed_answer']} | **{r['classification']}** |"
        )
    lines += [
        "",
        "## AMBIGUOUS notes",
        "",
        "- #6 Apomixis / #7 Biocontrol: NCERT TOC/heading answers are correct, but questions test table-of-contents recall rather than concept mastery → classified AMBIGUOUS (NEET suitability).",
        "",
        "## Limitations",
        "",
    ]
    for lim in report["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # post-write freeze recheck
    with engine.connect() as conn:
        after2 = snapshot(conn)
    assert after2 == before, "unexpected DB mutation during audit write"

    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "aggregate": report["aggregate"],
                "json": str(OUT_JSON),
                "md": str(OUT_MD),
                "db_unchanged": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
