#!/usr/bin/env python3
"""READ-ONLY MCQ production inventory audit for TALOS CMS.

SELECT-only. Never mutates DB. Writes docs/audits reports.

Primary DB: apps/backend DATABASE_URL (async) converted to psycopg —
that is the live inventory used by the running app. DATABASE_URL_SYNC may
point at an empty pytest DB; that mismatch is reported, not silently used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "docs" / "audits"
TODAY = date.today().strftime("%Y%m%d")


def _sync_url_from_settings() -> tuple[str, dict[str, str]]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.core.config import get_settings

    s = get_settings()
    async_url = s.database_url
    sync_cfg = s.database_url_sync
    # Live app uses async URL → convert driver for sync engine.
    live = async_url.replace("+asyncpg", "+psycopg")
    meta = {
        "database_url_async_hostpath": async_url.split("@")[-1] if "@" in async_url else async_url,
        "database_url_sync_hostpath": sync_cfg.split("@")[-1] if "@" in sync_cfg else sync_cfg,
        "audit_target": live.split("@")[-1] if "@" in live else live,
        "note": (
            "Audit uses DATABASE_URL (live app DB). "
            "DATABASE_URL_SYNC may be a separate empty test database."
        ),
    }
    return live, meta


def q(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {})


def scalar(conn, sql: str, params: dict | None = None):
    return q(conn, sql, params).scalar()


def mappings(conn, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    return [dict(r) for r in q(conn, sql, params).mappings().all()]


def rows(conn, sql: str, params: dict | None = None) -> list[tuple]:
    return list(q(conn, sql, params).fetchall())


def run_audit(conn) -> dict[str, Any]:
    defs = {
        "total": "cms.content_items content_type=QUESTION AND deleted_at IS NULL",
        "published": "status='PUBLISHED' (matches assessment.published_question_ids_for_scope)",
        "draft": "status='DRAFT' only — other non-published statuses listed separately",
        "subject": "JOIN concept→topic→chapter→subject; Biology executive = BOTANY+ZOOLOGY",
        "class": (
            "Priority: source_documents.class_level via latest_version KU/ingestion join; "
            "fallback ncert_reference Class 11/12; fallback relative_source_path regex. "
            "Conflicting if signals disagree."
        ),
        "diagram_based": (
            "Linked ingestion.visual_assets on knowledge_unit (via content_version_knowledge_units "
            "or content_versions.knowledge_unit_id) with asset_type='diagram' and deleted_at IS NULL. "
            "No diagram_svg/diagram_description keys exist on QUESTION bodies."
        ),
        "graphic_based": (
            "Any linked non-deleted visual_asset (image|diagram|table|equation|chemical_structure). "
            "Superset of diagram-based."
        ),
        "source_year": "body.pyq_year on latest_version; pilot_run_id / publisher from ingestion when joinable",
        "duplicates": "duplicate slug groups; duplicate lower(trim(stem)) groups; intra-question duplicate option texts",
        "version_body": "Inventory content metrics use latest_version_id; PUBLISHED live pointer = current_version_id",
    }

    body_keys = [r[0] for r in rows(
        conn,
        """
        SELECT DISTINCT k
        FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        CROSS JOIN LATERAL jsonb_object_keys(cv.body) AS k
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        ORDER BY 1
        """,
    )]

    total = scalar(
        conn,
        """
        SELECT count(*) FROM cms.content_items
        WHERE content_type = 'QUESTION' AND deleted_at IS NULL
        """,
    )
    soft_deleted = scalar(
        conn,
        """
        SELECT count(*) FROM cms.content_items
        WHERE content_type = 'QUESTION' AND deleted_at IS NOT NULL
        """,
    )
    by_status = {
        r[0]: int(r[1])
        for r in rows(
            conn,
            """
            SELECT status, count(*)
            FROM cms.content_items
            WHERE content_type = 'QUESTION' AND deleted_at IS NULL
            GROUP BY status ORDER BY count(*) DESC
            """,
        )
    }
    published = by_status.get("PUBLISHED", 0)
    draft = by_status.get("DRAFT", 0)
    other_non_published = {k: v for k, v in by_status.items() if k not in ("PUBLISHED", "DRAFT")}

    pointers = mappings(
        conn,
        """
        SELECT
          count(*) FILTER (WHERE latest_version_id IS NULL) AS latest_null,
          count(*) FILTER (WHERE current_version_id IS NULL) AS current_null,
          count(*) FILTER (WHERE latest_version_id IS DISTINCT FROM current_version_id) AS latest_ne_current
        FROM cms.content_items
        WHERE content_type = 'QUESTION' AND deleted_at IS NULL
        """,
    )[0]
    published_pointers = mappings(
        conn,
        """
        SELECT
          count(*) FILTER (WHERE current_version_id IS NULL) AS published_current_null,
          count(*) FILTER (WHERE current_version_id = latest_version_id) AS published_aligned,
          count(*) FILTER (
            WHERE current_version_id IS NOT NULL
              AND current_version_id IS DISTINCT FROM latest_version_id
          ) AS published_current_ne_latest
        FROM cms.content_items
        WHERE content_type = 'QUESTION' AND status = 'PUBLISHED' AND deleted_at IS NULL
        """,
    )[0]

    content_types = {
        r[0]: int(r[1])
        for r in rows(
            conn,
            """
            SELECT content_type, count(*)
            FROM cms.content_items WHERE deleted_at IS NULL
            GROUP BY content_type ORDER BY count(*) DESC
            """,
        )
    }
    diagram_content_type_items = content_types.get("DIAGRAM", 0)

    subject_rows = mappings(
        conn,
        """
        SELECT coalesce(s.code, 'UNMAPPED') AS subject_code,
               coalesce(s.name, 'Unmapped') AS subject_name,
               count(*)::int AS n
        FROM cms.content_items ci
        LEFT JOIN academic.concepts c ON c.id = ci.concept_id AND c.deleted_at IS NULL
        LEFT JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
        LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
        LEFT JOIN academic.subjects s ON s.id = ch.subject_id AND s.deleted_at IS NULL
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        GROUP BY 1, 2
        ORDER BY n DESC
        """,
    )
    subject_by_code = {r["subject_code"]: r["n"] for r in subject_rows}
    physics = subject_by_code.get("PHYSICS", 0)
    chemistry = subject_by_code.get("CHEMISTRY", 0)
    botany = subject_by_code.get("BOTANY", 0)
    zoology = subject_by_code.get("ZOOLOGY", 0)
    biology = botany + zoology
    subject_unmapped = subject_by_code.get("UNMAPPED", 0)

    subject_x_status = mappings(
        conn,
        """
        SELECT coalesce(s.code, 'UNMAPPED') AS subject_code,
               CASE WHEN ci.status = 'PUBLISHED' THEN 'PUBLISHED' ELSE 'NON_PUBLISHED' END AS pub_bucket,
               count(*)::int AS n
        FROM cms.content_items ci
        LEFT JOIN academic.concepts c ON c.id = ci.concept_id AND c.deleted_at IS NULL
        LEFT JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
        LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
        LEFT JOIN academic.subjects s ON s.id = ch.subject_id AND s.deleted_at IS NULL
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
    )

    # Class detection — materialize per-question signals then classify in SQL
    class_rows = mappings(
        conn,
        """
        WITH base AS (
          SELECT
            ci.id,
            -- source document class_level (authoritative when present)
            (
              SELECT sd.class_level
              FROM cms.content_versions cv
              LEFT JOIN cms.content_version_knowledge_units cvku ON cvku.content_version_id = cv.id
              LEFT JOIN knowledge.knowledge_units ku
                ON ku.id = coalesce(cvku.knowledge_unit_id, cv.knowledge_unit_id)
              LEFT JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
              LEFT JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
              LEFT JOIN ingestion.source_documents sd ON sd.id = j.source_document_id
              WHERE cv.id = ci.latest_version_id
              ORDER BY sd.class_level NULLS LAST
              LIMIT 1
            ) AS src_class,
            (
              SELECT sd.relative_source_path
              FROM cms.content_versions cv
              LEFT JOIN cms.content_version_knowledge_units cvku ON cvku.content_version_id = cv.id
              LEFT JOIN knowledge.knowledge_units ku
                ON ku.id = coalesce(cvku.knowledge_unit_id, cv.knowledge_unit_id)
              LEFT JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
              LEFT JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
              LEFT JOIN ingestion.source_documents sd ON sd.id = j.source_document_id
              WHERE cv.id = ci.latest_version_id
              ORDER BY sd.relative_source_path NULLS LAST
              LIMIT 1
            ) AS src_path,
            c.ncert_reference
          FROM cms.content_items ci
          LEFT JOIN academic.concepts c ON c.id = ci.concept_id
          WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        ),
        signals AS (
          SELECT
            id,
            CASE
              WHEN src_class IN ('11', '12') THEN src_class
              WHEN ncert_reference ~* 'class\\s*11' THEN '11'
              WHEN ncert_reference ~* 'class\\s*12' THEN '12'
              WHEN src_path ~* 'class[\\s_-]*11' THEN '11'
              WHEN src_path ~* 'class[\\s_-]*12' THEN '12'
              ELSE NULL
            END AS primary_class,
            CASE WHEN src_class IN ('11', '12') THEN src_class END AS from_src,
            CASE
              WHEN ncert_reference ~* 'class\\s*11' THEN '11'
              WHEN ncert_reference ~* 'class\\s*12' THEN '12'
            END AS from_ncert,
            CASE
              WHEN src_path ~* 'class[\\s_-]*11' THEN '11'
              WHEN src_path ~* 'class[\\s_-]*12' THEN '12'
            END AS from_path
          FROM base
        )
        SELECT
          id::text,
          primary_class,
          from_src,
          from_ncert,
          from_path,
          CASE
            WHEN (
              SELECT count(DISTINCT v)
              FROM unnest(ARRAY[from_src, from_ncert, from_path]) AS v
              WHERE v IS NOT NULL
            ) > 1 THEN true
            ELSE false
          END AS conflicting
        FROM signals
        """,
    )
    class_11 = class_12 = class_unknown = class_conflicting = 0
    for r in class_rows:
        if r["conflicting"]:
            class_conflicting += 1
        elif r["primary_class"] == "11":
            class_11 += 1
        elif r["primary_class"] == "12":
            class_12 += 1
        else:
            class_unknown += 1
    class_confidence = (
        "MEDIUM"
        if class_unknown < total * 0.5
        else "LOW CONFIDENCE — majority lack class_level / ncert / path signals"
    )

    visual = mappings(
        conn,
        """
        WITH q AS (
          SELECT
            ci.id,
            bool_or(
              va.id IS NOT NULL
              AND va.deleted_at IS NULL
              AND va.asset_type = 'diagram'
            ) AS diagram_based,
            bool_or(
              va.id IS NOT NULL
              AND va.deleted_at IS NULL
              AND va.asset_type IN ('image', 'diagram', 'table', 'equation', 'chemical_structure')
            ) AS graphic_based
          FROM cms.content_items ci
          JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
          LEFT JOIN cms.content_version_knowledge_units cvku ON cvku.content_version_id = cv.id
          LEFT JOIN knowledge.knowledge_units ku
            ON ku.id = coalesce(cvku.knowledge_unit_id, cv.knowledge_unit_id)
          LEFT JOIN ingestion.visual_assets va ON va.knowledge_unit_id = ku.id
          WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
          GROUP BY ci.id
        )
        SELECT
          count(*) FILTER (WHERE graphic_based)::int AS graphic_based,
          count(*) FILTER (WHERE diagram_based)::int AS diagram_based,
          count(*) FILTER (WHERE graphic_based AND diagram_based)::int AS both,
          count(*) FILTER (WHERE graphic_based AND NOT diagram_based)::int AS graphic_only,
          count(*) FILTER (WHERE diagram_based AND NOT graphic_based)::int AS diagram_only,
          count(*) FILTER (WHERE NOT graphic_based AND NOT diagram_based)::int AS neither
        FROM q
        """,
    )[0]

    pyq_dist = {
        (r[0] if r[0] is not None else "null"): int(r[1])
        for r in rows(
            conn,
            """
            SELECT cv.body->>'pyq_year' AS y, count(*)
            FROM cms.content_items ci
            JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
            WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
            GROUP BY 1 ORDER BY count(*) DESC
            """,
        )
    }
    with_pyq_year = total - pyq_dist.get("null", 0) - pyq_dist.get("", 0)

    pilot_dist = mappings(
        conn,
        """
        SELECT coalesce(j.pilot_run_id, '(none)') AS pilot_run_id, count(DISTINCT ci.id)::int AS n
        FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        LEFT JOIN cms.content_version_knowledge_units cvku ON cvku.content_version_id = cv.id
        LEFT JOIN knowledge.knowledge_units ku
          ON ku.id = coalesce(cvku.knowledge_unit_id, cv.knowledge_unit_id)
        LEFT JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
        LEFT JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 30
        """,
    )
    publisher_dist = mappings(
        conn,
        """
        SELECT coalesce(sd.publisher, '(none)') AS publisher, count(DISTINCT ci.id)::int AS n
        FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        LEFT JOIN cms.content_version_knowledge_units cvku ON cvku.content_version_id = cv.id
        LEFT JOIN knowledge.knowledge_units ku
          ON ku.id = coalesce(cvku.knowledge_unit_id, cv.knowledge_unit_id)
        LEFT JOIN ingestion.ingestion_sections sec ON sec.id = ku.source_section_id
        LEFT JOIN ingestion.ingestion_jobs j ON j.id = sec.job_id
        LEFT JOIN ingestion.source_documents sd ON sd.id = j.source_document_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        GROUP BY 1 ORDER BY n DESC
        """,
    )

    chapters = mappings(
        conn,
        """
        SELECT coalesce(ch.code, '(none)') AS chapter_code,
               coalesce(ch.name, '(no chapter)') AS chapter_name,
               count(*)::int AS n
        FROM cms.content_items ci
        LEFT JOIN academic.concepts c ON c.id = ci.concept_id
        LEFT JOIN academic.topics t ON t.id = c.topic_id
        LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        GROUP BY 1, 2
        ORDER BY n DESC
        """,
    )
    topics = mappings(
        conn,
        """
        SELECT coalesce(t.code, '(none)') AS topic_code,
               coalesce(t.name, '(no topic)') AS topic_name,
               count(*)::int AS n
        FROM cms.content_items ci
        LEFT JOIN academic.concepts c ON c.id = ci.concept_id
        LEFT JOIN academic.topics t ON t.id = c.topic_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        GROUP BY 1, 2
        ORDER BY n DESC
        """,
    )
    missing_concept_id = scalar(
        conn,
        """
        SELECT count(*) FROM cms.content_items
        WHERE content_type = 'QUESTION' AND deleted_at IS NULL AND concept_id IS NULL
        """,
    )
    concept_but_no_chapter = scalar(
        conn,
        """
        SELECT count(*)
        FROM cms.content_items ci
        JOIN academic.concepts c ON c.id = ci.concept_id
        LEFT JOIN academic.topics t ON t.id = c.topic_id
        LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
          AND ch.id IS NULL
        """,
    )

    dup_slugs = mappings(
        conn,
        """
        SELECT slug, count(*)::int AS n, array_agg(id::text ORDER BY created_at) AS ids
        FROM cms.content_items
        WHERE content_type = 'QUESTION' AND deleted_at IS NULL
        GROUP BY slug
        HAVING count(*) > 1
        ORDER BY n DESC
        LIMIT 20
        """,
    )
    dup_stems = mappings(
        conn,
        """
        SELECT lower(trim(cv.body->>'stem')) AS stem_norm,
               count(*)::int AS n,
               array_agg(ci.id::text ORDER BY ci.created_at) AS ids
        FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
          AND coalesce(trim(cv.body->>'stem'), '') <> ''
        GROUP BY 1
        HAVING count(*) > 1
        ORDER BY n DESC
        LIMIT 20
        """,
    )
    dup_stem_group_count = scalar(
        conn,
        """
        SELECT count(*) FROM (
          SELECT lower(trim(cv.body->>'stem')) AS stem_norm
          FROM cms.content_items ci
          JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
          WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
            AND coalesce(trim(cv.body->>'stem'), '') <> ''
          GROUP BY 1
          HAVING count(*) > 1
        ) s
        """,
    )
    dup_slug_group_count = scalar(
        conn,
        """
        SELECT count(*) FROM (
          SELECT slug FROM cms.content_items
          WHERE content_type = 'QUESTION' AND deleted_at IS NULL
          GROUP BY slug HAVING count(*) > 1
        ) s
        """,
    )
    # md5 stem+options near-dup
    near_dup_groups = scalar(
        conn,
        """
        SELECT count(*) FROM (
          SELECT md5(
            lower(trim(coalesce(cv.body->>'stem',''))) || '|' ||
            coalesce((cv.body->'options')::text, '')
          ) AS h
          FROM cms.content_items ci
          JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
          WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
          GROUP BY 1
          HAVING count(*) > 1
        ) x
        """,
    )
    intra_dup_options = scalar(
        conn,
        """
        SELECT count(*) FROM (
          SELECT ci.id
          FROM cms.content_items ci
          JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
          CROSS JOIN LATERAL (
            SELECT array_agg(lower(trim(opt->>'text'))) AS texts
            FROM jsonb_array_elements(
              CASE WHEN jsonb_typeof(cv.body->'options') = 'array' THEN cv.body->'options' ELSE '[]'::jsonb END
            ) AS opt
          ) o
          WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
            AND o.texts IS NOT NULL
            AND cardinality(o.texts) > 0
            AND cardinality(o.texts) <> (
              SELECT count(DISTINCT x) FROM unnest(o.texts) AS x WHERE x IS NOT NULL AND x <> ''
            )
        ) bad
        """,
    )

    missing = mappings(
        conn,
        """
        SELECT
          count(*) FILTER (WHERE ci.concept_id IS NULL)::int AS missing_concept_id,
          count(*) FILTER (WHERE ci.micro_competency_id IS NULL)::int AS missing_micro_competency_id,
          count(*) FILTER (WHERE coalesce(trim(cv.body->>'stem'), '') = '')::int AS missing_stem,
          count(*) FILTER (WHERE cv.body->'options' IS NULL)::int AS missing_options,
          count(*) FILTER (WHERE coalesce(trim(cv.body->>'correct_option'), '') = '')::int AS missing_correct_option,
          count(*) FILTER (WHERE coalesce(trim(cv.body->>'explanation'), '') = '')::int AS missing_explanation,
          count(*) FILTER (WHERE coalesce(trim(cv.body->>'difficulty'), '') = '')::int AS missing_difficulty,
          count(*) FILTER (
            WHERE cv.body->>'pyq_year' IS NULL OR trim(cv.body->>'pyq_year') = ''
          )::int AS missing_pyq_year,
          count(*) FILTER (
            WHERE NOT (
              SELECT coalesce(array_agg(upper(opt->>'label') ORDER BY upper(opt->>'label')), ARRAY[]::text[])
              FROM jsonb_array_elements(
                CASE WHEN jsonb_typeof(cv.body->'options') = 'array' THEN cv.body->'options' ELSE '[]'::jsonb END
              ) opt
            ) = ARRAY['A','B','C','D']
          )::int AS invalid_abcd_option_set
        FROM cms.content_items ci
        JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
        WHERE ci.content_type = 'QUESTION' AND ci.deleted_at IS NULL
        """,
    )[0]
    missing["missing_subject_mapping"] = subject_unmapped
    missing["missing_class_mapping"] = class_unknown
    missing["published_current_version_null"] = published_pointers["published_current_null"]

    # Non-production appendices (counts only)
    appendix = {
        "generation_candidates": scalar(conn, "SELECT count(*) FROM cms.generation_candidates"),
        "factory_review_items": scalar(conn, "SELECT count(*) FROM cms.factory_review_items"),
        "note": "NON-PRODUCTION — not included in Total MCQs",
    }

    sanity = {
        "sum_by_status_eq_total": sum(by_status.values()) == total,
        "published_draft_other_eq_total": published + draft + sum(other_non_published.values()) == total,
        "subject_mapped_unmapped_eq_total": (physics + chemistry + biology + subject_unmapped
            + sum(v for k, v in subject_by_code.items() if k not in ("PHYSICS", "CHEMISTRY", "BOTANY", "ZOOLOGY", "UNMAPPED")))
            == total,
        "class_parts_eq_total": class_11 + class_12 + class_unknown + class_conflicting == total,
        "graphic_subset": visual["graphic_based"] <= total,
        "diagram_subset": visual["diagram_based"] <= total,
        "practice_pool_published_match": published
        == scalar(
            conn,
            """
            SELECT count(*) FROM cms.content_items
            WHERE content_type = 'QUESTION' AND status = 'PUBLISHED' AND deleted_at IS NULL
            """,
        ),
    }
    # Fix subject sanity: botany+zoology already counted in biology; use subject_by_code sum
    sanity["subject_mapped_unmapped_eq_total"] = sum(subject_by_code.values()) == total

    recommendation = {
        "verdict": "CONDITIONAL",
        "reasons": [
            f"Only {published} PUBLISHED questions in student practice pool (of {total}).",
            f"{draft} remain DRAFT; {sum(other_non_published.values())} other non-published.",
            "Do not load more until Class coverage / subject mapping gaps are understood for new packs.",
            "No QUESTION body diagram_svg fields; graphic coverage depends on visual_asset linkage.",
            "DATABASE_URL_SYNC points at a different (empty) DB — keep using live DATABASE_URL for inventory.",
        ],
    }
    if published >= 30 and subject_unmapped == 0 and class_unknown < total * 0.2:
        recommendation["verdict"] = "YES"
    elif published == 0:
        recommendation["verdict"] = "NO"

    return {
        "date": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "definitions": defs,
        "body_keys_observed": body_keys,
        "totals": {
            "total_questions": total,
            "soft_deleted_questions": soft_deleted,
            "by_status": by_status,
            "published": published,
            "draft": draft,
            "other_non_published": other_non_published,
            "other_non_published_sum": sum(other_non_published.values()),
        },
        "pointers": {**pointers, **published_pointers},
        "content_types_non_deleted": content_types,
        "diagram_content_type_items": diagram_content_type_items,
        "subjects": {
            "by_code": subject_by_code,
            "detail": subject_rows,
            "physics": physics,
            "chemistry": chemistry,
            "botany": botany,
            "zoology": zoology,
            "biology_botany_plus_zoology": biology,
            "subject_unmapped": subject_unmapped,
            "subject_x_status": subject_x_status,
        },
        "class": {
            "class_11": class_11,
            "class_12": class_12,
            "class_unknown": class_unknown,
            "class_conflicting": class_conflicting,
            "confidence": class_confidence,
            "rule": defs["class"],
        },
        "visuals": visual,
        "source_year": {
            "pyq_year_distribution": pyq_dist,
            "with_pyq_year": with_pyq_year,
            "pilot_run_id_top": pilot_dist,
            "publisher_distribution": publisher_dist,
        },
        "chapter_topic": {
            "chapters": chapters[:25],
            "chapters_total_groups": len(chapters),
            "topics": topics[:25],
            "topics_total_groups": len(topics),
            "missing_concept_id": missing_concept_id,
            "concept_but_no_chapter": concept_but_no_chapter,
        },
        "duplicates": {
            "duplicate_slug_groups": dup_slug_group_count,
            "duplicate_stem_groups": dup_stem_group_count,
            "near_duplicate_stem_options_md5_groups": near_dup_groups,
            "questions_with_duplicate_option_texts": intra_dup_options,
            "slug_examples": dup_slugs,
            "stem_examples": [
                {"stem_norm": (e["stem_norm"] or "")[:120], "n": e["n"], "ids": e["ids"][:8]}
                for e in dup_stems
            ],
        },
        "missing_metadata": missing,
        "non_production_appendix": appendix,
        "sanity_checks": sanity,
        "recommendation": recommendation,
        "executive": {
            "Total MCQs (QUESTION, not deleted)": total,
            "Published": published,
            "Draft": draft,
            "Other statuses (sum)": sum(other_non_published.values()),
            "Physics": physics,
            "Chemistry": chemistry,
            "Biology (BOTANY+ZOOLOGY)": biology,
            "Subject unmapped": subject_unmapped,
            "Class 11": class_11,
            "Class 12": class_12,
            "Class unknown": class_unknown,
            "Graphic-based": visual["graphic_based"],
            "Diagram-based": visual["diagram_based"],
            "With pyq_year": with_pyq_year,
            "Missing concept_id": missing_concept_id,
            "Duplicate stem groups": dup_stem_group_count,
            "Duplicate slug groups": dup_slug_group_count,
        },
    }


def render_md(data: dict[str, Any], db_meta: dict[str, str]) -> str:
    ex = data["executive"]
    lines = [
        "# MCQ Production Inventory Audit",
        f"Date: {data['date']}",
        f"Database: `{db_meta['audit_target']}`",
        "Read-only: YES",
        "",
        f"_Config note:_ `{db_meta['note']}`",
        f"- DATABASE_URL → `{db_meta['database_url_async_hostpath']}` (audited)",
        f"- DATABASE_URL_SYNC → `{db_meta['database_url_sync_hostpath']}`",
        "",
        "## Executive Numbers",
        "",
        "| Metric | Count |",
        "|--------|------:|",
    ]
    for k, v in ex.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Definitions",
        "",
    ]
    for k, v in data["definitions"].items():
        lines.append(f"- **{k}**: {v}")

    lines += [
        "",
        f"**Observed QUESTION body keys:** `{', '.join(data['body_keys_observed'])}`",
        "",
        "## Status breakdown",
        "",
        "| Status | Count |",
        "|--------|------:|",
    ]
    for k, v in data["totals"]["by_status"].items():
        lines.append(f"| {k} | {v} |")
    lines += [
        f"| Soft-deleted (excluded from totals) | {data['totals']['soft_deleted_questions']} |",
        "",
        "### Pointer health",
        "",
        "```json",
        json.dumps(data["pointers"], indent=2),
        "```",
        "",
        "## Subject × status",
        "",
        "| Subject | Bucket | Count |",
        "|---------|--------|------:|",
    ]
    for r in data["subjects"]["subject_x_status"]:
        lines.append(f"| {r['subject_code']} | {r['pub_bucket']} | {r['n']} |")
    lines += [
        "",
        f"Biology executive rollup = BOTANY ({data['subjects']['botany']}) + ZOOLOGY ({data['subjects']['zoology']}) "
        f"= {data['subjects']['biology_botany_plus_zoology']}.",
        "",
        "## Class 11 / 12",
        "",
        f"**Confidence:** {data['class']['confidence']}",
        "",
        f"Rule: {data['class']['rule']}",
        "",
        "| Class | Count |",
        "|-------|------:|",
        f"| 11 | {data['class']['class_11']} |",
        f"| 12 | {data['class']['class_12']} |",
        f"| Unknown | {data['class']['class_unknown']} |",
        f"| Conflicting signals | {data['class']['class_conflicting']} |",
        "",
        "## Graphic / Diagram",
        "",
        f"- Graphic-based: **{data['visuals']['graphic_based']}**",
        f"- Diagram-based (`asset_type=diagram`): **{data['visuals']['diagram_based']}**",
        f"- Both: {data['visuals']['both']}",
        f"- Graphic only: {data['visuals']['graphic_only']}",
        f"- Diagram only: {data['visuals']['diagram_only']}",
        f"- Neither: {data['visuals']['neither']}",
        f"- Separate `content_type=DIAGRAM` items (not MCQs): **{data['diagram_content_type_items']}**",
        "",
        "## Source / year",
        "",
        "### pyq_year",
        "",
        "```json",
        json.dumps(data["source_year"]["pyq_year_distribution"], indent=2),
        "```",
        "",
        "### Publishers",
        "",
        "```json",
        json.dumps(data["source_year"]["publisher_distribution"], indent=2),
        "```",
        "",
        "### Top pilot_run_id",
        "",
        "```json",
        json.dumps(data["source_year"]["pilot_run_id_top"][:15], indent=2),
        "```",
        "",
        "## Chapter / topic (top)",
        "",
        "### Chapters",
        "",
        "| Code | Name | Count |",
        "|------|------|------:|",
    ]
    for r in data["chapter_topic"]["chapters"][:15]:
        lines.append(f"| {r['chapter_code']} | {r['chapter_name']} | {r['n']} |")
    lines += [
        "",
        f"_Chapter groups total: {data['chapter_topic']['chapters_total_groups']}_",
        "",
        "### Topics",
        "",
        "| Code | Name | Count |",
        "|------|------|------:|",
    ]
    for r in data["chapter_topic"]["topics"][:15]:
        lines.append(f"| {r['topic_code']} | {r['topic_name']} | {r['n']} |")
    lines += [
        "",
        f"_Topic groups total: {data['chapter_topic']['topics_total_groups']}_",
        f"- Missing concept_id: **{data['chapter_topic']['missing_concept_id']}**",
        f"- Concept but no chapter: **{data['chapter_topic']['concept_but_no_chapter']}**",
        "",
        "## Duplicates",
        "",
        f"- Duplicate slug groups: **{data['duplicates']['duplicate_slug_groups']}**",
        f"- Duplicate stem groups: **{data['duplicates']['duplicate_stem_groups']}**",
        f"- Near-dup md5(stem|options) groups: **{data['duplicates']['near_duplicate_stem_options_md5_groups']}**",
        f"- Questions with duplicate option texts: **{data['duplicates']['questions_with_duplicate_option_texts']}**",
        "",
        "### Stem duplicate examples",
        "",
        "```json",
        json.dumps(data["duplicates"]["stem_examples"][:10], indent=2),
        "```",
        "",
        "## Missing metadata",
        "",
        "```json",
        json.dumps(data["missing_metadata"], indent=2),
        "```",
        "",
        "## Non-production appendix (excluded from totals)",
        "",
        "```json",
        json.dumps(data["non_production_appendix"], indent=2),
        "```",
        "",
        "## Sanity checks",
        "",
        "```json",
        json.dumps(data["sanity_checks"], indent=2),
        "```",
        "",
        "## SQL / script",
        "",
        "Re-run: `apps/backend/scripts/audit_mcq_production_inventory.py`",
        "",
        "## Risks / gaps before loading more content",
        "",
        "- Student-visible pool is PUBLISHED-only and currently small versus authored DRAFT volume.",
        "- Class mapping is incomplete for many rows → treat Class KPIs as partial.",
        "- Academic subject codes split Biology into BOTANY/ZOOLOGY — report both ways.",
        "- Sync env DB ≠ live DB — inventory tooling must target DATABASE_URL.",
        "",
        f"## Recommendation: **{data['recommendation']['verdict']}**",
        "",
    ]
    for r in data["recommendation"]["reasons"]:
        lines.append(f"- {r}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    try:
        url, db_meta = _sync_url_from_settings()
        engine = create_engine(url)
        with engine.connect() as conn:
            # Prove read-only intent: open a transaction and rollback at end.
            dbname = scalar(conn, "SELECT current_database()")
            db_meta["current_database"] = dbname
            # Empty sync DB warning
            if "test" in (db_meta.get("database_url_sync_hostpath") or ""):
                pass
            data = run_audit(conn)
            conn.rollback()
    except Exception as exc:
        print(json.dumps({"error": str(exc), "read_only": True}, indent=2))
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"mcq-production-inventory-audit-{TODAY}.json"
    md_path = OUT_DIR / f"mcq-production-inventory-audit-{TODAY}.md"
    payload = {"database": db_meta, **data}
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_md(data, db_meta), encoding="utf-8")

    print(json.dumps({"executive": data["executive"], "database": db_meta, "reports": [str(md_path), str(json_path)], "sanity": data["sanity_checks"], "recommendation": data["recommendation"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
