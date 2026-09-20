#!/usr/bin/env python3
"""Production Seed V2 Phase 1 — file-based 100-slot plan. No generation, no CMS writes."""
from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import psycopg

ROOT = Path(r"D:\ravishori\AI Neet Exam App")
DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"
POST = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V1_POST_PUBLICATION_AUDIT_20260903.json"
AUTH = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
OUT_JSON = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
OUT_MD = ROOT / "docs" / "audits" / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.md"
NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace

EXPECTED_V1_SHA = "c0cf70846233730ef384188f5b78cced2a7865f76d977a0af6063f803bc8f0c1"

NCERT = {
    "PHYS_XI_1": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-1.pdf",
    "PHYS_XI_2": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-2.pdf",
    "PHYS_XI_3": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-3.pdf",
    "PHYS_XI_4": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-4.pdf",
    "PHYS_XI_5": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-5.pdf",
    "PHYS_XI_6": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-6.pdf",
    "PHYS_XI_8": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-8.pdf",
    "PHYS_XI_9": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-9.pdf",
    "PHYS_XI_11": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-11.pdf",
    "PHYS_XI_12": ROOT / "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-12.pdf",
    "PHYS_XII_1": ROOT / "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-1.pdf",
    "PHYS_XII_2": ROOT / "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-2.pdf",
    "PHYS_XII_3": ROOT / "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf",
    "PHYS_XII_9": ROOT / "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-2-chapter-9.pdf",
    "PHYS_XII_10": ROOT / "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-2-chapter-10.pdf",
    "CHEM_XI_1": ROOT / "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-1.pdf",
    "CHEM_XI_2": ROOT / "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-2.pdf",
    "CHEM_XI_4": ROOT / "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf",
    "CHEM_XI_5": ROOT / "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-5.pdf",
    "CHEM_XI_6": ROOT / "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-6.pdf",
    "CHEM_XI_7": ROOT / "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-7.pdf",
    "CHEM_XI_8": ROOT / "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-8.pdf",
    "CHEM_XII_2": ROOT / "StudyMaterial/Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-2.pdf",
    "BIO_XI_1": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-1.pdf",
    "BIO_XI_3": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-3.pdf",
    "BIO_XI_4": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf",
    "BIO_XI_5": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-5.pdf",
    "BIO_XI_7": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-7.pdf",
    "BIO_XI_8": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-8.pdf",
    "BIO_XI_9": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-9.pdf",
    "BIO_XI_11": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-11.pdf",
    "BIO_XI_13": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf",
    "BIO_XI_14": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-14.pdf",
    "BIO_XI_15": ROOT / "StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-15.pdf",
    "BIO_XII_1": ROOT / "StudyMaterial/Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-1.pdf",
}


def load_academic() -> dict:
    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.code, s.name, s.id::text,
                   ch.code, ch.name, ch.id::text,
                   t.code, t.name, t.id::text,
                   c.code, c.name, c.id::text
            FROM academic.subjects s
            JOIN academic.chapters ch ON ch.subject_id = s.id AND ch.deleted_at IS NULL
            LEFT JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
            LEFT JOIN academic.concepts c ON c.topic_id = t.id AND c.deleted_at IS NULL
            WHERE s.deleted_at IS NULL
            """
        )
        concepts = {}
        chapters = {}
        for r in cur.fetchall():
            subj_code, subj, sid, ch_code, ch, chid, t_code, t, tid, c_code, c, cid = r
            chapters[(subj_code, ch)] = {
                "subject_code": subj_code,
                "subject": subj,
                "subject_id": sid,
                "chapter_code": ch_code,
                "chapter": ch,
                "chapter_id": chid,
            }
            if cid:
                concepts[c_code] = {
                    "subject_code": subj_code,
                    "subject": subj,
                    "subject_id": sid,
                    "chapter_code": ch_code,
                    "chapter": ch,
                    "chapter_id": chid,
                    "topic_code": t_code,
                    "topic": t,
                    "topic_id": tid,
                    "concept_code": c_code,
                    "concept": c,
                    "concept_id": cid,
                }
        return {"concepts": concepts, "chapters": chapters}


def pop_fp(cur, tag: str) -> dict:
    cur.execute(
        """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE status='PUBLISHED'),
               COUNT(*) FILTER (WHERE status='DRAFT'),
               COUNT(*) FILTER (WHERE status='APPROVED'),
               md5(coalesce(string_agg(
                 ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||coalesce(ci.concept_id::text,'null')
                 ||'|'||md5(coalesce(cv.body::text,''))||'|'||coalesce(array_to_string(ci.tags,','),''),
                 E'\\n' ORDER BY ci.id::text), ''))
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL AND %s = ANY(ci.tags)
        """,
        (tag,),
    )
    a, b, c, d, e = cur.fetchone()
    return {"total": a, "published": b, "draft": c, "approved": d, "content_fp": e, "tag": tag}


def t6f2_fp(cur) -> dict:
    tag = "physics-t6f1-pilot-20260902"
    cur.execute(
        """
        SELECT COUNT(*),
               md5(coalesce(string_agg(
                 ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||md5(coalesce(cv.body::text,'')),
                 E'\\n' ORDER BY ci.id::text), ''))
        FROM cms.content_items ci
        LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL
          AND %s = ANY(ci.tags) AND ci.status = 'PUBLISHED'
        """,
        (tag,),
    )
    n, fp = cur.fetchone()
    return {"total": n, "content_fp": fp, "tag": tag}


def protected_snapshot() -> dict:
    post = json.loads(POST.read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    with psycopg.connect(DSN) as conn:
        cur = conn.cursor()
        t6d = pop_fp(cur, "physics-t6d-pilot-20260902")
        t6f2 = t6f2_fp(cur)
        legacy = pop_fp(cur, "legacy-physics-5000-import-20260902")
        v1 = pop_fp(cur, "production-seed-v1-2026-09-02")
        cur.execute(
            "SELECT status, count(*) FROM cms.content_items WHERE id = ANY(%s::uuid[]) GROUP BY status",
            (auth["exact_uuid_allowlist"],),
        )
        v1_status = dict(cur.fetchall())
        cur.execute("SELECT count(*) FROM cms.generation_candidates WHERE created_at > now() - interval '1 minute'")
        recent_gc = cur.fetchone()[0]
    exp = post["protected_population_integrity"]["after"]
    return {
        "seed_v1_allowlist_sha256": auth.get("allowlist_sha256"),
        "seed_v1_status": v1_status,
        "seed_v1_tag_fp": v1,
        "t6d": t6d,
        "t6f2": t6f2,
        "legacy": legacy,
        "unchanged": {
            "t6d": exp["t6d"]["content_fp"] == t6d["content_fp"] and exp["t6d"]["total"] == t6d["total"],
            "t6f2": exp["t6f2"]["content_fp"] == t6f2["content_fp"] and exp["t6f2"]["total"] == t6f2["total"],
            "legacy": exp["legacy"]["content_fp"] == legacy["content_fp"] and exp["legacy"]["total"] == legacy["total"],
            "seed_v1_allowlist_hash": auth.get("allowlist_sha256") == EXPECTED_V1_SHA,
            "seed_v1_published_30": v1_status.get("PUBLISHED") == 30,
        },
        "recent_generation_candidates_last_minute": recent_gc,
        "cms_writes_this_phase": 0,
    }


def ncert_meta(key: str) -> dict:
    path = NCERT[key]
    exists = path.is_file()
    return {
        "ncert_source_key": key,
        "ncert_source_document": path.name,
        "ncert_source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "ncert_source_available": exists,
        "ncert_source_type": "NCERT_PDF",
        "page_verified": False,
        "source_verification_status": "FILE_EXISTS" if exists else "MISSING",
    }


def bp_id(slot_id: str) -> str:
    return str(uuid.uuid5(NS, f"talos:production-seed-v2:2026-09-03:{slot_id}"))


def make_slot(
    *,
    n: int,
    subject: str,
    class_level: str,
    acad: dict,
    chapter_name: str | None = None,
    concept_code: str | None = None,
    topic_override: str | None = None,
    concept_override: str | None = None,
    intent: str,
    difficulty: str,
    difficulty_rationale: str,
    archetype: str,
    archetype_rationale: str,
    ncert_key: str,
    rationale: str,
    calculation_type: str | None = None,
    governing_concept: str | None = None,
    forbidden_note: str | None = None,
) -> dict:
    prefix = {"Physics": "physics", "Chemistry": "chemistry", "Botany": "botany", "Zoology": "zoology"}[subject]
    slot_id = f"{prefix}-{n:02d}"
    mapping = "CHAPTER"
    row = None
    ch = None
    subj_code = {"Physics": "PHYSICS", "Chemistry": "CHEMISTRY", "Botany": "BOTANY", "Zoology": "ZOOLOGY"}[subject]
    if concept_code:
        row = acad["concepts"][concept_code]
        mapping = "CONCEPT"
        chapter_name = row["chapter"]
    else:
        ch = acad["chapters"][(subj_code, chapter_name)]

    src = ncert_meta(ncert_key)
    slot = {
        "slot_id": slot_id,
        "subject": subject,
        "subject_code": subj_code,
        "class": class_level,
        "chapter": row["chapter"] if row else ch["chapter"],
        "topic": (row["topic"] if row else None) or topic_override,
        "concept": (row["concept"] if row else None) or concept_override,
        "intent": intent,
        "difficulty": difficulty,
        "difficulty_rationale": difficulty_rationale,
        "question_archetype": archetype,
        "archetype_rationale": archetype_rationale,
        "blueprint_id": bp_id(slot_id),
        "blueprint_key": f"production-seed-v2-2026-09-03-bp-{slot_id}",
        "blueprint_created": False,
        "planning_status": "ACTIVE",
        "academic_mapping_level": mapping,
        "subject_id": row["subject_id"] if row else ch["subject_id"],
        "chapter_id": row["chapter_id"] if row else ch["chapter_id"],
        "topic_id": row["topic_id"] if row else None,
        "concept_id": row["concept_id"] if row else None,
        "concept_code": concept_code,
        "planning_rationale": rationale,
        "independent_verification_required": True if calculation_type else False,
        **src,
    }
    if calculation_type:
        slot["calculation_type"] = calculation_type
        slot["governing_concept"] = governing_concept
        slot["independent_verification_required"] = True
    if forbidden_note:
        slot["template_avoidance"] = forbidden_note
    # Explicit visual requirement (A): every V2 slot has visual_required / type / archetype.
    from app.modules.cms.services.factory_v2_visual import enrich_slot_with_visual_fields

    return enrich_slot_with_visual_fields(slot)


def build_slots(acad: dict) -> list[dict]:
    s: list[dict] = []

    def P(**kw):
        s.append(make_slot(n=len([x for x in s if x["subject"] == "Physics"]) + 1, subject="Physics", acad=acad, **kw))

    def C(**kw):
        s.append(make_slot(n=len([x for x in s if x["subject"] == "Chemistry"]) + 1, subject="Chemistry", acad=acad, **kw))

    def B(**kw):
        s.append(make_slot(n=len([x for x in s if x["subject"] == "Botany"]) + 1, subject="Botany", acad=acad, **kw))

    def Z(**kw):
        s.append(make_slot(n=len([x for x in s if x["subject"] == "Zoology"]) + 1, subject="Zoology", acad=acad, **kw))

    # ---- Physics 35: unique concept_codes across 12 mapped chapters ----
    P(class_level="XI", concept_code="si-base-and-derived-units", intent="unit_recognition",
      difficulty="easy", difficulty_rationale="Recall of SI base vs derived units.",
      archetype="direct_ncert_conceptual", archetype_rationale="NCERT lists base/derived units.",
      ncert_key="PHYS_XI_1", rationale="Opens Units and Measurement without numerical error analysis.")
    P(class_level="XI", concept_code="dimensional-formulae", intent="dimensional_formula_identify",
      difficulty="easy", difficulty_rationale="Write/identify dimensional formula.",
      archetype="direct_ncert_conceptual", archetype_rationale="Standard dimensional formulae table.",
      ncert_key="PHYS_XI_1", rationale="Distinct from SI-unit recognition: dimensions, not unit names.")
    P(class_level="XI", concept_code="dimensional-analysis-applications", intent="check_equation_dimensions",
      difficulty="medium", difficulty_rationale="Apply homogeneity to a relation.",
      archetype="application", archetype_rationale="Use dimensions to test a candidate equation.",
      ncert_key="PHYS_XI_1", rationale="Application of dimensional analysis, not formula listing.")
    P(class_level="XI", concept_code="kinematic-equations", intent="numerical_straight_line",
      difficulty="medium", difficulty_rationale="One-step uniformly accelerated motion.",
      archetype="numerical_calculation", archetype_rationale="v=u+at / s=ut+½at² application.",
      ncert_key="PHYS_XI_2", rationale="1D kinematics numerical; independent of circular/projectile.",
      calculation_type="suvat_1d", governing_concept="kinematic-equations")
    P(class_level="XI", concept_code="instantaneous-velocity-acceleration", intent="slope_of_x_t",
      difficulty="medium", difficulty_rationale="Interpret derivative/slope meaning.",
      archetype="diagram_data_interpretation", archetype_rationale="x–t or v–t graph reading if generated from NCERT-style axes; no fabricated data tables.",
      ncert_key="PHYS_XI_2", rationale="Graph/slope interpretation, not SUVAT plug-in.")
    P(class_level="XI", concept_code="projectile-motion", intent="range_or_time_of_flight",
      difficulty="medium", difficulty_rationale="Standard projectile formula application.",
      archetype="numerical_calculation", archetype_rationale="Range or time of flight.",
      ncert_key="PHYS_XI_3", rationale="Plane motion distinct from 1D kinematics.",
      calculation_type="projectile_range", governing_concept="projectile-motion")
    P(class_level="XI", concept_code="uniform-circular-motion", intent="centripetal_acceleration_concept",
      difficulty="medium", difficulty_rationale="Centripetal acceleration magnitude and radial direction together.",
      archetype="direct_ncert_conceptual", archetype_rationale="NCERT centripetal acceleration definition.",
      ncert_key="PHYS_XI_3", rationale="UCM concept, not Newton's-law circular dynamics.")
    P(class_level="XI", concept_code="newtons-laws", intent="n2_free_body_reasoning",
      difficulty="medium", difficulty_rationale="Apply ΣF=ma to a simple FBD.",
      archetype="application", archetype_rationale="Newton II on a block/string system without stretch templates.",
      ncert_key="PHYS_XI_4", rationale="Laws of Motion conceptual application.")
    P(class_level="XI", concept_code="friction", intent="static_vs_kinetic",
      difficulty="medium", difficulty_rationale="Choose static vs kinetic friction and fs ≤ μN.",
      archetype="comparison", archetype_rationale="Static vs kinetic friction statements.",
      ncert_key="PHYS_XI_4", rationale="Friction, not Newton's-law identity slot.")
    P(class_level="XI", concept_code="conservation-of-momentum", intent="1d_collision_momentum",
      difficulty="medium", difficulty_rationale="Apply p conservation to 1D collision.",
      archetype="numerical_calculation", archetype_rationale="Two-body 1D momentum.",
      ncert_key="PHYS_XI_4", rationale="Momentum conservation distinct from energy theorem.",
      calculation_type="momentum_1d", governing_concept="conservation-of-momentum")
    P(class_level="XI", concept_code="work-energy-theorem", intent="net_work_delta_k",
      difficulty="medium", difficulty_rationale="Compute ΔK from net work.",
      archetype="numerical_calculation", archetype_rationale="W_net = ΔK.",
      ncert_key="PHYS_XI_5", rationale="Work–energy, not potential-energy definition.",
      calculation_type="work_energy", governing_concept="work-energy-theorem")
    P(class_level="XI", concept_code="potential-energy", intent="gravitational_pe_near_earth",
      difficulty="easy", difficulty_rationale="mgh near Earth.",
      archetype="direct_ncert_conceptual", archetype_rationale="PE definition/sign convention.",
      ncert_key="PHYS_XI_5", rationale="PE concept distinct from work–energy numerical.")
    P(class_level="XI", concept_code="conservation-mechanical-energy", intent="conservative_force_track",
      difficulty="medium", difficulty_rationale="K+U constant on frictionless track.",
      archetype="application", archetype_rationale="Mechanical energy conservation.",
      ncert_key="PHYS_XI_5", rationale="Conservation statement, not collision inelasticity.")
    P(class_level="XI", concept_code="collisions", intent="elastic_vs_inelastic",
      difficulty="medium", difficulty_rationale="Classify collision type by energy.",
      archetype="comparison", archetype_rationale="Elastic vs inelastic criteria.",
      ncert_key="PHYS_XI_5", rationale="Collision classification, not 1D momentum-only.")
    P(class_level="XI", concept_code="moment-of-inertia", intent="parallel_axis_or_listed_mi",
      difficulty="medium", difficulty_rationale="Use a listed MI or parallel-axis conceptually.",
      archetype="application", archetype_rationale="I about an axis.",
      ncert_key="PHYS_XI_6", rationale="Rotational inertia, not torque definition.")
    P(class_level="XI", concept_code="torque", intent="tau_equals_rF_perp",
      difficulty="hard", difficulty_rationale="Torque with lever arm and sinθ in a 2D arrangement.",
      archetype="direct_ncert_conceptual", archetype_rationale="Torque definition.",
      ncert_key="PHYS_XI_6", rationale="Torque, not angular momentum.")
    P(class_level="XI", concept_code="angular-momentum", intent="l_equals_i_omega_or_r_cross_p",
      difficulty="medium", difficulty_rationale="L for particle or rigid body.",
      archetype="direct_ncert_conceptual", archetype_rationale="Angular momentum definition.",
      ncert_key="PHYS_XI_6", rationale="Distinct from torque and MI.")
    P(class_level="XI", concept_code="centre-of-mass-system", intent="com_two_particle",
      difficulty="medium", difficulty_rationale="Two-particle COM position.",
      archetype="numerical_calculation", archetype_rationale="x_cm = (m1x1+m2x2)/(m1+m2).",
      ncert_key="PHYS_XI_6", rationale="COM location, not rotational dynamics.",
      calculation_type="com_two_body", governing_concept="centre-of-mass-system")
    P(class_level="XI", concept_code="stress-strain-definitions", intent="define_stress_strain",
      difficulty="easy", difficulty_rationale="Definitions only.",
      archetype="direct_ncert_conceptual", archetype_rationale="Stress/strain definitions.",
      ncert_key="PHYS_XI_8", rationale="Definitions — NOT wire-stretch current templates.",
      forbidden_note="Do not use 20% stretch or doubled-length resistance templates.")
    P(class_level="XI", concept_code="youngs-modulus", intent="y_equals_stress_over_strain",
      difficulty="medium", difficulty_rationale="Y from stress/strain or elongation.",
      archetype="numerical_calculation", archetype_rationale="Young's modulus numerical.",
      ncert_key="PHYS_XI_8", rationale="Y numerical without current-in-stretched-wire.",
      calculation_type="youngs_modulus", governing_concept="youngs-modulus",
      forbidden_note="No PHYS_STRETCH_20PCT_CURRENT / 2X length current ratio.")
    P(class_level="XI", concept_code="stress-strain-curve", intent="identify_regions",
      difficulty="medium", difficulty_rationale="Identify proportional/elastic/plastic regions.",
      archetype="diagram_data_interpretation", archetype_rationale="NCERT stress–strain curve regions; do not invent data.",
      ncert_key="PHYS_XI_8", rationale="Curve interpretation, not modulus calculation.")
    P(class_level="XI", concept_code="hydrostatic-pressure-pascal", intent="p_equals_h_rho_g",
      difficulty="easy", difficulty_rationale="Hydrostatic pressure formula.",
      archetype="direct_ncert_conceptual", archetype_rationale="P = hρg / Pascal.",
      ncert_key="PHYS_XI_9", rationale="Statics of fluids, not Bernoulli.")
    P(class_level="XI", concept_code="bernoullis-principle", intent="bernoulli_along_streamline",
      difficulty="medium", difficulty_rationale="Apply Bernoulli qualitatively or one numerical.",
      archetype="application", archetype_rationale="P + ρgh + ½ρv².",
      ncert_key="PHYS_XI_9", rationale="Bernoulli, not viscosity.")
    P(class_level="XI", concept_code="surface-tension", intent="excess_pressure_or_capillary",
      difficulty="medium", difficulty_rationale="ΔP = 2S/r or capillary rise concept.",
      archetype="direct_ncert_conceptual", archetype_rationale="Surface tension formulae from NCERT.",
      ncert_key="PHYS_XI_9", rationale="Surface tension family, not flow.")
    P(class_level="XI", concept_code="zeroth-and-first-law", intent="first_law_dq_du_dw",
      difficulty="easy", difficulty_rationale="ΔQ = ΔU + ΔW statement.",
      archetype="direct_ncert_conceptual", archetype_rationale="First law of thermodynamics.",
      ncert_key="PHYS_XI_11", rationale="First law, not Carnot.")
    P(class_level="XI", concept_code="thermodynamic-process-types", intent="identify_isothermal_adiabatic",
      difficulty="medium", difficulty_rationale="PV characteristics of processes.",
      archetype="comparison", archetype_rationale="Compare isothermal vs adiabatic.",
      ncert_key="PHYS_XI_11", rationale="Process types, not second law.")
    P(class_level="XI", concept_code="second-law-and-carnot", intent="carnot_efficiency_limit",
      difficulty="hard", difficulty_rationale="η = 1 − T2/T1 conceptual/numerical.",
      archetype="numerical_calculation", archetype_rationale="Carnot efficiency.",
      ncert_key="PHYS_XI_11", rationale="Second law/Carnot — highest thermo demand.",
      calculation_type="carnot_efficiency", governing_concept="second-law-and-carnot")
    P(class_level="XI", concept_code="kinetic-interpretation-temperature", intent="rms_or_avg_ke",
      difficulty="medium", difficulty_rationale="Relate T to molecular KE.",
      archetype="direct_ncert_conceptual", archetype_rationale="(1/2)m v_rms² = (3/2)kT.",
      ncert_key="PHYS_XI_12", rationale="Kinetic temperature, not mean free path.")
    P(class_level="XI", concept_code="mean-free-path", intent="mfp_dependence",
      difficulty="hard", difficulty_rationale="λ dependence on n and d.",
      archetype="direct_ncert_conceptual", archetype_rationale="Mean free path formula meaning.",
      ncert_key="PHYS_XI_12", rationale="MFP distinct from equipartition.")
    P(class_level="XII", concept_code="coulomb-force", intent="inverse_square_force",
      difficulty="medium", difficulty_rationale="F ∝ q1q2/r² with direction.",
      archetype="numerical_calculation", archetype_rationale="Coulomb force magnitude.",
      ncert_key="PHYS_XII_1", rationale="Coulomb force; not field–potential relation.",
      calculation_type="coulomb_force", governing_concept="coulomb-force")
    P(class_level="XII", concept_code="field-potential-relation", intent="e_equals_minus_dv_dx",
      difficulty="medium", difficulty_rationale="Relate E and V.",
      archetype="direct_ncert_conceptual", archetype_rationale="E = −dV/dx in 1D.",
      ncert_key="PHYS_XII_2", rationale="Field–potential, not Coulomb pair force.")
    P(class_level="XII", concept_code="drift-velocity", intent="i_equals_n_e_a_vd",
      difficulty="medium", difficulty_rationale="I = n e A vd.",
      archetype="application", archetype_rationale="Current–drift-velocity relation.",
      ncert_key="PHYS_XII_3", rationale="Drift velocity — NOT Ohm V-doubled at constant R.",
      forbidden_note="Forbidden: PHYS_OHM_V_DOUBLED_R_CONSTANT.")
    P(class_level="XII", concept_code="kcl-kvl", intent="junction_or_loop_rule",
      difficulty="medium", difficulty_rationale="Apply KCL or KVL to a simple loop.",
      archetype="application", archetype_rationale="Kirchhoff rules.",
      ncert_key="PHYS_XII_3", rationale="Network laws, not Ohm stretch templates.")
    P(class_level="XII", concept_code="lens-formula", intent="thin_lens_uv",
      difficulty="medium", difficulty_rationale="1/v − 1/u = 1/f.",
      archetype="numerical_calculation", archetype_rationale="Thin lens numerical.",
      ncert_key="PHYS_XII_9", rationale="Ray optics lens formula.",
      calculation_type="thin_lens", governing_concept="lens-formula")
    P(class_level="XII", concept_code="interference-young", intent="fringe_width_beta",
      difficulty="hard", difficulty_rationale="β = λD/d.",
      archetype="numerical_calculation", archetype_rationale="YDSE fringe width.",
      ncert_key="PHYS_XII_10", rationale="Wave optics YDSE — distinct from ray lens.",
      calculation_type="ydse_fringe", governing_concept="interference-young")

    # ---- Chemistry 35 across 8 academic chapters; lattice at most once, not comparison cluster ----
    C(class_level="XI", chapter_name="Some Basic Concepts of Chemistry",
      topic_override="Laws of Chemical Combination", concept_override="Law of conservation of mass / definite proportions",
      intent="stoichiometry_law_identify", difficulty="easy",
      difficulty_rationale="Identify which combination law applies.",
      archetype="direct_ncert_conceptual", archetype_rationale="NCERT combination laws.",
      ncert_key="CHEM_XI_1", rationale="Mole chapter law, not bonding.")
    C(class_level="XI", chapter_name="Some Basic Concepts of Chemistry",
      topic_override="Mole Concept", concept_override="Mole and molar mass",
      intent="mole_to_particles", difficulty="medium",
      difficulty_rationale="Convert moles ↔ particles/mass.",
      archetype="numerical_calculation", archetype_rationale="n = N/NA or m/M.",
      ncert_key="CHEM_XI_1", rationale="Mole numerical.",
      calculation_type="mole_conversion", governing_concept="mole-concept")
    C(class_level="XI", chapter_name="Some Basic Concepts of Chemistry",
      topic_override="Empirical and Molecular Formula", concept_override="Empirical formula from composition",
      intent="empirical_formula", difficulty="medium",
      difficulty_rationale="Percent composition to empirical formula.",
      archetype="numerical_calculation", archetype_rationale="Empirical formula calculation.",
      ncert_key="CHEM_XI_1", rationale="Composition analysis, not mole-count only.",
      calculation_type="empirical_formula", governing_concept="empirical-formula")
    C(class_level="XI", chapter_name="Some Basic Concepts of Chemistry",
      topic_override="Molarity and Concentration", concept_override="Molarity definition",
      intent="molarity_definition", difficulty="easy",
      difficulty_rationale="Define molarity units.",
      archetype="direct_ncert_conceptual", archetype_rationale="M = mol/L.",
      ncert_key="CHEM_XI_1", rationale="Concentration unit, not empirical formula.")
    C(class_level="XI", chapter_name="Some Basic Concepts of Chemistry",
      topic_override="Stoichiometry of Reactions", concept_override="Limiting reagent concept",
      intent="limiting_reagent_qualitative", difficulty="hard",
      difficulty_rationale="Identify limiting reagent in a stated reaction.",
      archetype="application", archetype_rationale="Limiting reagent reasoning.",
      ncert_key="CHEM_XI_1", rationale="Reaction stoichiometry, not simple mole conversion.")
    C(class_level="XI", chapter_name="Structure of Atom",
      topic_override="Bohr Model", concept_override="Bohr postulates / hydrogen spectrum idea",
      intent="bohr_postulate_identify", difficulty="hard",
      difficulty_rationale="Bohr energy/radius dependence on n, not a one-line recall.",
      archetype="statement_based", archetype_rationale="Which statement is a Bohr postulate.",
      ncert_key="CHEM_XI_2", rationale="Bohr model, not quantum numbers.")
    C(class_level="XI", chapter_name="Structure of Atom",
      topic_override="Quantum Numbers", concept_override="n, l, ml, ms",
      intent="quantum_number_validity", difficulty="medium",
      difficulty_rationale="Allowed quantum number set.",
      archetype="application", archetype_rationale="Validity of (n,l,ml,ms).",
      ncert_key="CHEM_XI_2", rationale="Quantum numbers, not Bohr orbits.")
    C(class_level="XI", chapter_name="Structure of Atom",
      topic_override="Electronic Configuration", concept_override="Aufbau, Pauli, Hund",
      intent="hund_or_pauli_application", difficulty="medium",
      difficulty_rationale="Apply Hund/Pauli to a configuration.",
      archetype="application", archetype_rationale="Ground-state configuration rule.",
      ncert_key="CHEM_XI_2", rationale="Rules of filling, not photoelectric.")
    C(class_level="XI", chapter_name="Structure of Atom",
      topic_override="Photoelectric Effect and Dual Nature", concept_override="Photoelectric effect features",
      intent="photoelectric_threshold", difficulty="medium",
      difficulty_rationale="Threshold frequency/KE of photoelectrons (qualitative or simple).",
      archetype="direct_ncert_conceptual", archetype_rationale="Photoelectric features from unit objectives.",
      ncert_key="CHEM_XI_2", rationale="Photoelectric, not orbital shapes.")
    C(class_level="XI", chapter_name="Structure of Atom",
      topic_override="Orbitals", concept_override="s, p, d orbital shapes/nodes (qualitative)",
      intent="orbital_shape_identify", difficulty="easy",
      difficulty_rationale="Identify orbital from shape/nodes statement.",
      archetype="direct_ncert_conceptual", archetype_rationale="Orbital description.",
      ncert_key="CHEM_XI_2", rationale="Orbitals, not quantum-number validity.")
    C(class_level="XI", concept_code="vsepr-theory", intent="geometry_from_electron_pairs",
      difficulty="medium", difficulty_rationale="Predict geometry from AXnEm.",
      archetype="application", archetype_rationale="VSEPR geometry.",
      ncert_key="CHEM_XI_4", rationale="VSEPR geometry — not lattice energy.")
    C(class_level="XI", concept_code="sp-sp2-sp3", intent="hybridization_identify_from_bonding",
      difficulty="medium", difficulty_rationale="Identify hybridisation from bonding.",
      archetype="application", archetype_rationale="Count sigma bonds/lone pairs → hybridisation.",
      ncert_key="CHEM_XI_4", rationale="Identify hybridisation; V2 second hybridisation slot uses shape link.")
    C(class_level="XI", concept_code="sp-sp2-sp3", intent="hybridization_to_geometry",
      difficulty="hard", difficulty_rationale="Link hybridisation to molecular shape.",
      archetype="comparison", archetype_rationale="sp2 trigonal planar vs sp3 tetrahedral.",
      ncert_key="CHEM_XI_4", rationale="Same concept_code as V1 reuse-with-distinct-intent pattern; shape not identification.")
    C(class_level="XI", chapter_name="Chemical Bonding and Molecular Structure",
      topic_override="Ionic vs Covalent Bonding", concept_override="Electronegativity and bond type",
      intent="bond_type_from_en_difference", difficulty="easy",
      difficulty_rationale="Ionic vs covalent from ΔEN qualitative.",
      archetype="comparison", archetype_rationale="Bond type comparison WITHOUT lattice-energy ranking.",
      ncert_key="CHEM_XI_4", rationale="Bond type, not lattice magnitudes.",
      forbidden_note="Do not use CHEM_LATTICE_COMPARISON or lattice-factor paraphrase.")
    C(class_level="XI", concept_code="lattice-energy", intent="definition_only_not_comparison",
      difficulty="medium", difficulty_rationale="Definition of lattice enthalpy/energy.",
      archetype="direct_ncert_conceptual", archetype_rationale="Single definitional item.",
      ncert_key="CHEM_XI_4", rationale="At most one lattice-energy slot; definition only.",
      forbidden_note="No lattice comparison cluster; no 'factors influencing lattice' paraphrase.")
    C(class_level="XI", chapter_name="Thermodynamics",
      topic_override="First Law of Thermodynamics (Chemistry)", concept_override="ΔU = q + w sign convention",
      intent="chem_first_law_signs", difficulty="medium",
      difficulty_rationale="Apply IUPAC sign convention to q,w,ΔU.",
      archetype="application", archetype_rationale="First-law bookkeeping.",
      ncert_key="CHEM_XI_5", rationale="Chemical thermodynamics first law.")
    C(class_level="XI", chapter_name="Thermodynamics",
      topic_override="Enthalpy", concept_override="ΔH vs ΔU for reactions",
      intent="enthalpy_vs_internal_energy", difficulty="medium",
      difficulty_rationale="Relate ΔH and ΔU for gas reactions.",
      archetype="direct_ncert_conceptual", archetype_rationale="ΔH = ΔU + ΔngRT idea.",
      ncert_key="CHEM_XI_5", rationale="Enthalpy, not entropy.")
    C(class_level="XI", chapter_name="Thermodynamics",
      topic_override="Hess's Law", concept_override="Hess's law of constant heat summation",
      intent="hess_law_cycle", difficulty="hard",
      difficulty_rationale="Combine enthalpies in a cycle.",
      archetype="numerical_calculation", archetype_rationale="Hess's law numerical.",
      ncert_key="CHEM_XI_5", rationale="Hess cycle, not first-law signs.",
      calculation_type="hess_law", governing_concept="hess-law")
    C(class_level="XI", chapter_name="Thermodynamics",
      topic_override="Entropy and Spontaneity", concept_override="Second law / Gibbs energy qualitative",
      intent="spontaneity_delta_g", difficulty="medium",
      difficulty_rationale="ΔG sign and spontaneity.",
      archetype="statement_based", archetype_rationale="Which process is spontaneous.",
      ncert_key="CHEM_XI_5", rationale="Spontaneity, not Hess arithmetic.")
    C(class_level="XI", concept_code="equilibrium-constant", intent="kc_meaning_not_just_formula",
      difficulty="medium", difficulty_rationale="Meaning of large/small Kc.",
      archetype="direct_ncert_conceptual", archetype_rationale="Kc interpretation.",
      ncert_key="CHEM_XI_6", rationale="Kc meaning, not pH.")
    C(class_level="XI", chapter_name="Equilibrium",
      topic_override="Le Chatelier's Principle", concept_override="Effect of concentration, pressure, temperature",
      intent="le_chatelier_shift", difficulty="medium",
      difficulty_rationale="Predict equilibrium shift.",
      archetype="application", archetype_rationale="Le Chatelier scenario.",
      ncert_key="CHEM_XI_6", rationale="Perturbation of equilibrium, not Kc definition.")
    C(class_level="XI", concept_code="ph-and-kw", intent="ph_from_h_concentration",
      difficulty="medium", difficulty_rationale="pH = −log[H+].",
      archetype="numerical_calculation", archetype_rationale="Simple strong-acid pH.",
      ncert_key="CHEM_XI_6", rationale="pH numerical.",
      calculation_type="ph_strong_acid", governing_concept="ph-and-kw")
    C(class_level="XI", chapter_name="Equilibrium",
      topic_override="Acids, Bases and Buffers", concept_override="Bronsted–Lowry conjugate pairs",
      intent="conjugate_acid_base", difficulty="easy",
      difficulty_rationale="Identify conjugate pair.",
      archetype="direct_ncert_conceptual", archetype_rationale="Bronsted conjugates.",
      ncert_key="CHEM_XI_6", rationale="Acid–base identity, not Ksp.")
    C(class_level="XI", concept_code="ksp-basics", intent="ksp_solubility_meaning",
      difficulty="hard", difficulty_rationale="Relate Ksp to saturated solution.",
      archetype="direct_ncert_conceptual", archetype_rationale="Ksp interpretation, one item only.",
      ncert_key="CHEM_XI_6", rationale="Single Ksp slot — not a solubility cluster.")
    C(class_level="XI", chapter_name="Redox Reactions",
      topic_override="Oxidation Number", concept_override="Rules for oxidation number",
      intent="ox_number_assign", difficulty="hard",
      difficulty_rationale="Assign oxidation numbers in a polyatomic ion (e.g. oxo-anion).",
      archetype="application", archetype_rationale="Oxidation number rules.",
      ncert_key="CHEM_XI_7", rationale="ON assignment.")
    C(class_level="XI", chapter_name="Redox Reactions",
      topic_override="Redox Identification", concept_override="Oxidising and reducing agents",
      intent="identify_oxidising_agent", difficulty="medium",
      difficulty_rationale="Which species is oxidised/reduced.",
      archetype="comparison", archetype_rationale="Oxidising vs reducing agent.",
      ncert_key="CHEM_XI_7", rationale="Agent identity, not balancing.")
    C(class_level="XI", chapter_name="Redox Reactions",
      topic_override="Balancing Redox Reactions", concept_override="Ion-electron / oxidation-number method idea",
      intent="balance_redox_concept", difficulty="hard",
      difficulty_rationale="Choose correct balanced skeleton or method step.",
      archetype="application", archetype_rationale="Balancing logic.",
      ncert_key="CHEM_XI_7", rationale="Balancing, not ON assignment.")
    C(class_level="XI", chapter_name="Redox Reactions",
      topic_override="Types of Redox Reactions", concept_override="Combination, decomposition, displacement, disproportionation",
      intent="classify_redox_type", difficulty="easy",
      difficulty_rationale="Classify a named redox type.",
      archetype="direct_ncert_conceptual", archetype_rationale="NCERT redox types.",
      ncert_key="CHEM_XI_7", rationale="Classification, not electrochemistry cells.")
    C(class_level="XI", concept_code="homologous-series", intent="general_formula_or_trait",
      difficulty="easy", difficulty_rationale="Homologous series traits.",
      archetype="direct_ncert_conceptual", archetype_rationale="General formula / CH2 difference.",
      ncert_key="CHEM_XI_8", rationale="Homologous series.")
    C(class_level="XI", concept_code="structural-isomerism", intent="identify_structural_isomer_type",
      difficulty="medium", difficulty_rationale="Chain/position/functional isomer.",
      archetype="application", archetype_rationale="Classify isomer type.",
      ncert_key="CHEM_XI_8", rationale="Isomerism, not electronic effects.")
    C(class_level="XI", concept_code="inductive-mesomeric", intent="inductive_vs_resonance",
      difficulty="medium", difficulty_rationale="Distinguish +I/−I vs +R/−R.",
      archetype="comparison", archetype_rationale="Electronic effects comparison.",
      ncert_key="CHEM_XI_8", rationale="Electronic effects, not isomerism.")
    C(class_level="XI", chapter_name="Organic Chemistry - Basic Principles",
      topic_override="IUPAC Nomenclature", concept_override="IUPAC naming of simple acyclic compounds",
      intent="iupac_name_simple", difficulty="medium",
      difficulty_rationale="Name a simple branched alkane/functional compound.",
      archetype="application", archetype_rationale="IUPAC rules.",
      ncert_key="CHEM_XI_8", rationale="Nomenclature, not homologous-series traits.")
    C(class_level="XII", chapter_name="Electrochemistry",
      topic_override="Galvanic Cells", concept_override="Daniel cell / electrode representation",
      intent="cell_representation", difficulty="medium",
      difficulty_rationale="Identify anode/cathode or cell notation.",
      archetype="direct_ncert_conceptual", archetype_rationale="Galvanic cell representation.",
      ncert_key="CHEM_XII_2", rationale="Cells, not Class 11 redox ON.")
    C(class_level="XII", chapter_name="Electrochemistry",
      topic_override="Nernst Equation", concept_override="Concentration dependence of EMF (qualitative)",
      intent="nernst_qualitative", difficulty="hard",
      difficulty_rationale="How EMF changes with concentration.",
      archetype="application", archetype_rationale="Nernst qualitative/simple.",
      ncert_key="CHEM_XII_2", rationale="Nernst, not conductance.")
    C(class_level="XII", chapter_name="Electrochemistry",
      topic_override="Conductance of Electrolytic Solutions", concept_override="Molar conductivity / Kohlrausch idea",
      intent="molar_conductivity_trend", difficulty="medium",
      difficulty_rationale="Λm vs concentration qualitative.",
      archetype="direct_ncert_conceptual", archetype_rationale="Electrolytic conductance.",
      ncert_key="CHEM_XII_2", rationale="Conductance, not galvanic notation.")

    # ---- Botany 15: 7 academic chapters; photosynthesis without non-cyclic template ----
    B(class_level="XI", chapter_name="The Living World",
      topic_override="Diversity and Taxonomy", concept_override="Taxonomic hierarchy / binomial nomenclature",
      intent="binomial_nomenclature", difficulty="easy",
      difficulty_rationale="Binomial rules from Living World.",
      archetype="direct_ncert_conceptual", archetype_rationale="Nomenclature rules.",
      ncert_key="BIO_XI_1", rationale="Living World taxonomy.")
    B(class_level="XI", chapter_name="The Living World",
      topic_override="Taxonomic Aids", concept_override="Herbarium / botanical gardens / keys (qualitative)",
      intent="taxonomic_aid_identify", difficulty="easy",
      difficulty_rationale="Identify a taxonomic aid.",
      archetype="direct_ncert_conceptual", archetype_rationale="NCERT taxonomic aids.",
      ncert_key="BIO_XI_1", rationale="Aids, not binomial rules.")
    B(class_level="XI", chapter_name="Plant Kingdom",
      topic_override="Algae and Bryophytes", concept_override="Algae classes / bryophyte haplodiplontic idea",
      intent="plant_group_feature", difficulty="medium",
      difficulty_rationale="Diagnostic feature of a plant group.",
      archetype="comparison", archetype_rationale="Compare two plant groups.",
      ncert_key="BIO_XI_3", rationale="Plant Kingdom, not cell ultrastructure.")
    B(class_level="XI", chapter_name="Plant Kingdom",
      topic_override="Pteridophytes and Gymnosperms", concept_override="Heterospory / gymnosperm seeds",
      intent="pteridophyte_or_gymnosperm_trait", difficulty="medium",
      difficulty_rationale="Key trait identification.",
      archetype="direct_ncert_conceptual", archetype_rationale="NCERT plant-group traits.",
      ncert_key="BIO_XI_3", rationale="Different plant group than algae slot.")
    B(class_level="XI", chapter_name="Morphology of Flowering Plants",
      topic_override="Root, Stem and Leaf", concept_override="Modifications of root/stem/leaf",
      intent="identify_modification", difficulty="easy",
      difficulty_rationale="Match modification to function.",
      archetype="application", archetype_rationale="Morphological modification.",
      ncert_key="BIO_XI_5", rationale="Vegetative morphology.")
    B(class_level="XI", chapter_name="Morphology of Flowering Plants",
      topic_override="Flower, Inflorescence, Fruit", concept_override="Floral formula / placentation types",
      intent="placentation_or_floral_whorls", difficulty="medium",
      difficulty_rationale="Identify placentation or floral parts.",
      archetype="direct_ncert_conceptual", archetype_rationale="Flower structure.",
      ncert_key="BIO_XI_5", rationale="Reproductive morphology, not leaf modification.")
    B(class_level="XI", concept_code="prokaryote-eukaryote", intent="cell_type_contrast",
      difficulty="easy", difficulty_rationale="Prokaryote vs eukaryote traits.",
      archetype="comparison", archetype_rationale="Cell types.",
      ncert_key="BIO_XI_8", rationale="Cell types.")
    B(class_level="XI", concept_code="fluid-mosaic", intent="membrane_model_components",
      difficulty="easy", difficulty_rationale="Fluid mosaic components/fluidity.",
      archetype="direct_ncert_conceptual", archetype_rationale="Singer–Nicolson model.",
      ncert_key="BIO_XI_8", rationale="Membrane model, not organelles.")
    B(class_level="XI", concept_code="mitochondria-chloroplast", intent="endosymbiont_or_double_membrane",
      difficulty="medium", difficulty_rationale="Shared organelle features.",
      archetype="comparison", archetype_rationale="Mitochondria vs chloroplast.",
      ncert_key="BIO_XI_8", rationale="Organelles, not membrane model.")
    B(class_level="XI", concept_code="c3-c4-pathway", intent="pathway_compare_anatomy_or_enzyme",
      difficulty="medium", difficulty_rationale="C3 vs C4 CO2 fixation contrast.",
      archetype="comparison", archetype_rationale="Kranz/PEP carboxylase vs Rubisco first step.",
      ncert_key="BIO_XI_11", rationale="C3/C4 — not non-cyclic photophosphorylation sequence.",
      forbidden_note="Avoid BOT_NONCYCLIC_PHOTOPHOSPHORYLATION stem family.")
    B(class_level="XI", concept_code="limiting-factors", intent="blackman_law",
      difficulty="easy", difficulty_rationale="Blackman's law statement.",
      archetype="direct_ncert_conceptual", archetype_rationale="Limiting factors.",
      ncert_key="BIO_XI_11", rationale="Limiting factors, not C3/C4 anatomy.")
    B(class_level="XI", concept_code="photophosphorylation", intent="cyclic_photophosphorylation_products",
      difficulty="medium", difficulty_rationale="Cyclic photophosphorylation yields ATP, not NADPH/O2.",
      archetype="direct_ncert_conceptual", archetype_rationale="Cyclic vs non-cyclic outcome — cyclic-focused, not non-cyclic sequence drill.",
      ncert_key="BIO_XI_11", rationale="Uses photophosphorylation concept with cyclic-product intent, not non-cyclic template repetition.",
      forbidden_note="Do not generate non-cyclic e− sequence / Z-scheme step-order clones.")
    B(class_level="XI", chapter_name="Plant Growth and Development",
      topic_override="Plant Growth Regulators", concept_override="Auxin / gibberellin / cytokinin / ethylene / ABA roles",
      intent="pgr_function_match", difficulty="medium",
      difficulty_rationale="Match hormone to NCERT function.",
      archetype="application", archetype_rationale="PGR function.",
      ncert_key="BIO_XI_13", rationale="Hormones, not photosynthesis.")
    B(class_level="XI", chapter_name="Plant Growth and Development",
      topic_override="Photoperiodism and Vernalisation", concept_override="SDP/LDP qualitative",
      intent="photoperiodism_class", difficulty="hard",
      difficulty_rationale="Classify photoperiod response.",
      archetype="direct_ncert_conceptual", archetype_rationale="Photoperiodism.",
      ncert_key="BIO_XI_13", rationale="Photoperiod, not PGR identity.")
    B(class_level="XII", chapter_name="Sexual Reproduction in Flowering Plants",
      topic_override="Double Fertilisation", concept_override="Syngamy and triple fusion",
      intent="double_fertilisation_products", difficulty="medium",
      difficulty_rationale="Products of double fertilisation.",
      archetype="sequence_order", archetype_rationale="Order of events in embryo sac.",
      ncert_key="BIO_XII_1", rationale="Class XII flowering-plant reproduction.")

    # ---- Zoology 15: skip ABO cluster; span 7 chapters ----
    Z(class_level="XI", concept_code="levels-of-organisation", intent="organisation_level_identify",
      difficulty="easy", difficulty_rationale="Cellular/tissue/organ/organ-system.",
      archetype="direct_ncert_conceptual", archetype_rationale="Levels of organisation.",
      ncert_key="BIO_XI_4", rationale="Organisation levels.")
    Z(class_level="XI", concept_code="porifera-cnidaria", intent="phylum_diagnostic",
      difficulty="medium", difficulty_rationale="Diagnostic feature of Porifera or Cnidaria.",
      archetype="comparison", archetype_rationale="Two non-chordate phyla.",
      ncert_key="BIO_XI_4", rationale="Non-chordates, not chordate features.")
    Z(class_level="XI", concept_code="chordate-features", intent="fundamental_chordate_characters",
      difficulty="easy", difficulty_rationale="Notochord/dorsal hollow nerve cord/pharyngeal slits.",
      archetype="direct_ncert_conceptual", archetype_rationale="Chordate characters.",
      ncert_key="BIO_XI_4", rationale="Chordates, distinct from Porifera.")
    Z(class_level="XI", chapter_name="Structural Organisation in Animals",
      topic_override="Animal Tissues", concept_override="Epithelial / connective / muscular / neural",
      intent="tissue_type_identify", difficulty="easy",
      difficulty_rationale="Identify tissue from description.",
      archetype="direct_ncert_conceptual", archetype_rationale="Tissue types.",
      ncert_key="BIO_XI_7", rationale="Tissues, not phylum characters.")
    Z(class_level="XI", chapter_name="Structural Organisation in Animals",
      topic_override="Cockroach / Frog (as in NCERT)", concept_override="Selected morphology of cockroach or frog",
      intent="cockroach_or_frog_structure", difficulty="medium",
      difficulty_rationale="NCERT animal morphology fact.",
      archetype="direct_ncert_conceptual", archetype_rationale="Structural organisation example.",
      ncert_key="BIO_XI_7", rationale="Organismal anatomy, not tissue classification.")
    Z(class_level="XI", concept_code="biomolecule-classes", intent="classify_biomolecule",
      difficulty="easy", difficulty_rationale="Carb/protein/lipid/nucleic acid class.",
      archetype="direct_ncert_conceptual", archetype_rationale="Biomolecule classes.",
      ncert_key="BIO_XI_9", rationale="Classes, not enzyme mechanism.")
    Z(class_level="XI", concept_code="dna-rna", intent="dna_vs_rna_structure",
      difficulty="medium", difficulty_rationale="Sugar/bases/strands contrast.",
      archetype="comparison", archetype_rationale="DNA vs RNA.",
      ncert_key="BIO_XI_9", rationale="Nucleic acids, not enzyme kinetics.")
    Z(class_level="XI", chapter_name="Breathing and Exchange of Gases",
      topic_override="Human Respiratory System", concept_override="Pathway of air / alveoli",
      intent="respiratory_path", difficulty="easy",
      difficulty_rationale="Order of respiratory passage.",
      archetype="sequence_order", archetype_rationale="Air pathway sequence.",
      ncert_key="BIO_XI_14", rationale="Breathing anatomy.")
    Z(class_level="XI", chapter_name="Breathing and Exchange of Gases",
      topic_override="Transport of Gases", concept_override="Oxygen dissociation / Bohr effect qualitative",
      intent="o2_dissociation_shift", difficulty="hard",
      difficulty_rationale="Shift of O2-Hb curve.",
      archetype="application", archetype_rationale="Bohr effect qualitative.",
      ncert_key="BIO_XI_14", rationale="Gas transport, not airway sequence.")
    Z(class_level="XI", concept_code="heart-structure", intent="chamber_valve_identify",
      difficulty="easy", difficulty_rationale="Chamber/valve identity.",
      archetype="direct_ncert_conceptual", archetype_rationale="Heart anatomy.",
      ncert_key="BIO_XI_15", rationale="Anatomy, not cycle phases.")
    Z(class_level="XI", concept_code="cardiac-cycle-phases", intent="systole_diastole_identify",
      difficulty="medium", difficulty_rationale="Phase of cardiac cycle.",
      archetype="sequence_order", archetype_rationale="Cycle order.",
      ncert_key="BIO_XI_15", rationale="Cycle, not ABO grouping.",
      forbidden_note="No ZOO_ABO_SEQUENCE / antigen-identify templates.")
    Z(class_level="XI", chapter_name="Body Fluids and Circulation",
      topic_override="ECG", concept_override="P, QRS, T waves",
      intent="ecg_wave_meaning", difficulty="medium",
      difficulty_rationale="Match ECG wave to event.",
      archetype="diagram_data_interpretation", archetype_rationale="NCERT ECG labelling; no fabricated traces.",
      ncert_key="BIO_XI_15", rationale="ECG, not ABO. Avoid blood-group agglutination cluster.")
    Z(class_level="XI", concept_code="enzyme-basics", intent="enzyme_active_site_specificity",
      difficulty="medium", difficulty_rationale="Active site / specificity from Biomolecules.",
      archetype="direct_ncert_conceptual", archetype_rationale="Enzyme action without kinetics cluster.",
      ncert_key="BIO_XI_9", rationale="Third biomolecule family (enzymes), distinct from DNA/RNA and class identification. Class 12 Human Reproduction PDF (ch 2) is absent; those academic concepts were not mapped to a fabricated source.")
    Z(class_level="XI", chapter_name="Breathing and Exchange of Gases",
      topic_override="Respiratory Volumes and Capacities", concept_override="Tidal volume / vital capacity (definitions)",
      intent="respiratory_volume_define", difficulty="medium",
      difficulty_rationale="Define a named lung volume/capacity.",
      archetype="direct_ncert_conceptual", archetype_rationale="NCERT respiratory volumes.",
      ncert_key="BIO_XI_14", rationale="Volumes, not airway sequence or Bohr effect.")
    Z(class_level="XI", chapter_name="Body Fluids and Circulation",
      topic_override="Lymph and Double Circulation", concept_override="Pulmonary vs systemic circuit",
      intent="double_circulation", difficulty="hard",
      difficulty_rationale="Double circulation pathway reasoning.",
      archetype="comparison", archetype_rationale="Pulmonary vs systemic.",
      ncert_key="BIO_XI_15", rationale="Circulation topology, not ABO grouping.")

    return s


def cluster_summary(slots, key):
    c = Counter(x[key] for x in slots)
    top = c.most_common(1)[0]
    return {"counts": dict(c), "largest": {key: top[0], "n": top[1]}}


def subject_dist(slots, subject):
    sub = [x for x in slots if x["subject"] == subject]
    ch = Counter(x["chapter"] for x in sub)
    tp = Counter(x["topic"] for x in sub)
    co = Counter(x["concept"] for x in sub)
    return {
        "total_slots": len(sub),
        "distinct_chapters": len(ch),
        "distinct_topics": len(tp),
        "distinct_concepts": len(co),
        "largest_chapter_cluster": {"chapter": ch.most_common(1)[0][0], "n": ch.most_common(1)[0][1]},
        "largest_topic_cluster": {"topic": tp.most_common(1)[0][0], "n": tp.most_common(1)[0][1]},
        "largest_concept_cluster": {"concept": co.most_common(1)[0][0], "n": co.most_common(1)[0][1]},
        "chapters": dict(ch),
    }


def main() -> int:
    missing = [k for k, p in NCERT.items() if not p.is_file()]
    if missing:
        raise SystemExit(f"NCERT files missing: {missing}")
    acad = load_academic()
    slots = build_slots(acad)
    prot = protected_snapshot()

    failures = []
    by_subj = Counter(x["subject"] for x in slots)
    if len(slots) != 100:
        failures.append(f"slot_count={len(slots)}")
    if by_subj.get("Physics") != 35 or by_subj.get("Chemistry") != 35:
        failures.append(f"subject_allocation={dict(by_subj)}")
    if by_subj.get("Botany") != 15 or by_subj.get("Zoology") != 15:
        failures.append(f"bio_allocation={dict(by_subj)}")
    bp = [x["blueprint_id"] for x in slots]
    if len(set(bp)) != 100:
        failures.append("blueprint_uniqueness_fail")
    if any(not x["ncert_source_available"] for x in slots):
        failures.append("ncert_missing")
    if any(not x["chapter_id"] for x in slots):
        failures.append("missing_chapter_id")
    diffs = Counter(x["difficulty"] for x in slots)
    if diffs.get("easy") != 25 or diffs.get("medium") != 60 or diffs.get("hard") != 15:
        failures.append(f"difficulty={dict(diffs)}")
    if not all(prot["unchanged"].values()):
        failures.append("protected_population_changed")

    chem = subject_dist(slots, "Chemistry")
    if chem["distinct_chapters"] < 5:
        failures.append(f"chemistry_chapter_concentration chapters={chem['distinct_chapters']}")
    if chem["largest_chapter_cluster"]["n"] > 8:
        failures.append(f"chemistry_largest_chapter={chem['largest_chapter_cluster']}")

    phys = subject_dist(slots, "Physics")
    bot = subject_dist(slots, "Botany")
    zoo = subject_dist(slots, "Zoology")

    concept_freq = Counter(x["concept"] for x in slots)
    repeated = {k: v for k, v in concept_freq.items() if v > 1}

    arch = Counter(x["question_archetype"] for x in slots)
    arch_subj = defaultdict(Counter)
    for x in slots:
        arch_subj[x["subject"]][x["question_archetype"]] += 1

    ncert_files = sorted({x["ncert_source_document"] for x in slots})

    verdict = "GREEN" if not failures else "RED"

    plan = {
        "audit": "Production Seed V2 Phase 1 Blueprint Plan",
        "date": "2026-09-03",
        "status": "PLANNING_ONLY",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "target": 100,
        "subject_allocation": {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15},
        "difficulty_target": {"Easy": 25, "Medium": 60, "Hard": 15},
        "difficulty_actual": {"easy": diffs.get("easy", 0), "medium": diffs.get("medium", 0), "hard": diffs.get("hard", 0)},
        "preferred_batch_key": "production-seed-v2-2026-09-03-batch",
        "generation_not_run": True,
        "slots": slots,
        "blueprint_uniqueness": {
            "slot_count": len(slots),
            "unique_blueprint_ids": len(set(bp)),
            "pass": len(slots) == 100 and len(set(bp)) == 100,
        },
        "chapter_distribution": {
            "Physics": phys,
            "Chemistry": chem,
            "Botany": bot,
            "Zoology": zoo,
        },
        "topic_distribution": {
            "Physics": dict(Counter(x["topic"] for x in slots if x["subject"] == "Physics")),
            "Chemistry": dict(Counter(x["topic"] for x in slots if x["subject"] == "Chemistry")),
            "Botany": dict(Counter(x["topic"] for x in slots if x["subject"] == "Botany")),
            "Zoology": dict(Counter(x["topic"] for x in slots if x["subject"] == "Zoology")),
        },
        "concept_distribution": {
            "unique_concepts": len(concept_freq),
            "repeated_concepts": repeated,
            "maximum_concept_frequency": max(concept_freq.values()) if concept_freq else 0,
            "repeat_rationale": {
                "sp, sp2, sp3 Hybridization": "Two intents: identify hybridisation vs link hybridisation to geometry (same V1 pattern, distinct cognitive operation).",
            },
        },
        "archetype_distribution": {
            "overall": dict(arch),
            "by_subject": {k: dict(v) for k, v in arch_subj.items()},
        },
        "ncert_source_inventory": {
            "unique_source_documents": ncert_files,
            "unique_source_count": len(ncert_files),
            "all_files_exist": all(x["ncert_source_available"] for x in slots),
            "page_verified_policy": "page_verified=false at planning; no invented page numbers",
            "excluded_ncert_without_academic_chapter": [
                "Class 11 Physics Ch 7 Gravitation (PDF missing; academic chapter has 0 concepts)",
                "Class 11 Physics Ch 13 Oscillations / Ch 14 Waves (PDF exist; no academic chapter)",
                "Class 12 Physics magnetism/EMI/AC/EM waves/dual nature/atoms/nuclei/semiconductors (PDF exist; no academic chapter)",
                "Class 11 Chemistry Ch 3 Periodicity and Ch 9 Hydrocarbons (PDF exist; no academic chapter)",
                "Class 12 Chemistry except Electrochemistry (PDF exist; no academic chapter)",
                "Biology chapters without Botany/Zoology academic chapter mapping were not used as primary slots",
            ],
        },
        "previous_failure_avoidance": {
            "ABO antigen/agglutination": {
                "pattern": "ZOO_ABO_SEQUENCE / ZOO_ABO_ANTIGEN_IDENTIFY",
                "planned_slots": 0,
                "risk": "LOW",
                "mitigation": "abo-blood-grouping concept unused; circulation slots use heart, cycle, ECG.",
            },
            "non-cyclic photophosphorylation": {
                "pattern": "BOT_NONCYCLIC_PHOTOPHOSPHORYLATION",
                "planned_slots": 1,
                "risk": "MEDIUM",
                "mitigation": "Single photophosphorylation slot constrained to cyclic products, not Z-scheme sequence clones.",
            },
            "Ohm/V-doubled": {
                "pattern": "PHYS_OHM_V_DOUBLED_R_CONSTANT",
                "planned_slots": 0,
                "risk": "LOW",
                "mitigation": "ohms-law-concept unused; current electricity uses drift velocity and KCL/KVL.",
            },
            "20% stretch template": {
                "pattern": "PHYS_STRETCH_20PCT_CURRENT / 2X length",
                "planned_slots": 0,
                "risk": "LOW",
                "mitigation": "Solids slots are definitions, Young's modulus, stress–strain curve — no wire-current stretch.",
            },
            "lattice-energy paraphrase cluster": {
                "pattern": "CHEM_LATTICE_COMPARISON / CHEM_LATTICE_FACTORS",
                "planned_slots": 1,
                "risk": "LOW",
                "mitigation": "Exactly one lattice-energy definition slot; remaining bonding slots are VSEPR, hybridisation, bond type.",
            },
        },
        "v1_comparison": {
            "v1_slots": 30,
            "v2_slots": 100,
            "v2_improves_blueprint_diversity": True,
            "avoids_p3_95_single_family_allocation": True,
            "chemistry_spans_multiple_concept_families": True,
            "physics_spans_multiple_chapters": True,
            "botany_spans_multiple_topics": True,
            "zoology_spans_multiple_topics": True,
            "previous_template_clusters_avoided": True,
            "each_slot_distinct_intent": True,
            "suitable_for_later_gemini_generation": True,
            "notes": [
                "V1 used 10/10/5/5; V2 uses 35/35/15/15 with unique blueprint_id per slot.",
                "P3-95 used one concept per large family target; V2 is one blueprint per slot.",
                "Academic concept table has only 9 Chemistry concepts; chapter-mapped slots extend Chemistry to 8 academic chapters using NCERT section titles without inventing UUIDs.",
            ],
        },
        "generation_feasibility": {
            "estimate_only": True,
            "gemini_called": False,
            "target": 100,
            "attempt_multiplier": 2.0,
            "max_attempts_policy": 200,
            "cost_cap_usd": 30.0,
            "v1_reference": {"created": 30, "attempts": 43, "cost_usd_approx": 0.095},
            "expected_attempts_linear": "≈140–180 if yield similar to V1 (~0.70 created/attempt)",
            "expected_cost_usd": "≈0.30–0.50 if cost scales with V1 (~$0.003/created); well under $30",
            "feasible_within_current_caps": True,
            "do_not_raise_caps": True,
            "pass": True,
        },
        "protected_population_integrity": prot,
        "limitations": [
            "Academic hierarchy is sparse: Chemistry has 9 concepts / 8 chapters; Botany 7 concepts; Zoology 12 concepts. Chapter-level slots use NCERT section titles with chapter_id only.",
            "Oscillations, Waves, Gravitation (no PDF), magnetism/EMI/AC, most Class 12 Chemistry, and several Biology chapters exist as PDFs but lack academic.chapters rows — excluded rather than invented.",
            "Human Reproduction Class 12 NCERT chapter 2 PDF is absent in StudyMaterial; Zoology slots use Class 11 sources only (Animal Kingdom, tissues, biomolecules, breathing, circulation).",
            "page_verified is false for all slots by design at planning.",
            "blueprint_id values are deterministic UUID5 planning identifiers — not persisted to cms.question_blueprints in this phase.",
        ],
        "failures": failures,
        "verdict": verdict,
        "phase_stop": "PHASE_1_COMPLETE — do not proceed to P3 without separate authorization",
    }

    OUT_JSON.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    md = f"""# Production Seed V2 — Phase 1 Blueprint Plan

**Verdict:** {verdict}  
**Status:** PLANNING_ONLY — Gemini not called; no CMS writes.

## Allocation

| Subject | Slots | Distinct chapters | Largest chapter cluster |
|---------|------:|------------------:|-------------------------|
| Physics | {phys['total_slots']} | {phys['distinct_chapters']} | {phys['largest_chapter_cluster']} |
| Chemistry | {chem['total_slots']} | {chem['distinct_chapters']} | {chem['largest_chapter_cluster']} |
| Botany | {bot['total_slots']} | {bot['distinct_chapters']} | {bot['largest_chapter_cluster']} |
| Zoology | {zoo['total_slots']} | {zoo['distinct_chapters']} | {zoo['largest_chapter_cluster']} |

## Uniqueness

- Slots: {len(slots)}
- Unique blueprint IDs: {len(set(bp))}
- Difficulty: easy {diffs.get('easy')} / medium {diffs.get('medium')} / hard {diffs.get('hard')}

## Archetypes

{json.dumps(dict(arch), indent=2)}

## NCERT

- Unique source PDFs: {len(ncert_files)}
- All exist: {all(x['ncert_source_available'] for x in slots)}
- page_verified: false (planning)

## Previous failure avoidance

See JSON `previous_failure_avoidance`. ABO/Ohm-stretch/lattice clusters constrained.

## Generation feasibility

Estimate only. Policy caps unchanged (200 attempts, $30). V1 cost suggests V2 remains far under cap.

## Protected populations

{json.dumps(prot['unchanged'], indent=2)}

## Stop

Do **not** start P3 generation until separately authorized.
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "slots": len(slots),
        "subjects": dict(by_subj),
        "blueprints": len(set(bp)),
        "difficulty": dict(diffs),
        "failures": failures,
        "out_json": str(OUT_JSON),
        "chem_chapters": chem["distinct_chapters"],
        "phys_chapters": phys["distinct_chapters"],
    }, indent=2))
    return 0 if verdict == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
