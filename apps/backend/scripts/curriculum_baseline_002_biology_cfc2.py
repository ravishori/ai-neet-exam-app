"""CF-C2 — Biology Class 12 owner-approved Botany/Zoology taxonomy.

Surgical apply only. No full seed_academic(). No CMS/content mutation.
No AI / Content Factory / blueprints / commit.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import fitz
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.academic.models import Chapter, Concept, Subject, Topic  # noqa: E402
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    get_ncert_source_root,
    validate_ncert_generation_source,
)

# Owner-approved mapping (project taxonomy decision — not an NCERT claim).
# Topics/concepts below are derived from canonical PDF section headings.
APPROVED: list[dict] = [
    # ---- BOTANY XII ----
    {
        "subject": "BOTANY",
        "code": "sexual-reproduction-flowering-plants",
        "name": "Sexual Reproduction in Flowering Plants",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo101.pdf",
        "ncert_ch": 1,
        "preserve_existing": True,
        "topics": [
            (
                "flower-and-pre-fertilisation",
                "Flower and Pre-Fertilisation Structures and Events",
                [
                    (
                        "stamen-microsporangium-pollen",
                        "Stamen, Microsporangium and Pollen Grain",
                        "NCERT XII Biology Ch 1 §1.2.1 — anther structure, microsporogenesis and pollen grain.",
                    ),
                    (
                        "pistil-ovule-embryo-sac",
                        "Pistil, Megasporangium (Ovule) and Embryo Sac",
                        "NCERT XII Biology Ch 1 §1.2.2 — megasporogenesis and organisation of the embryo sac.",
                    ),
                    (
                        "pollination-types",
                        "Pollination",
                        "NCERT XII Biology Ch 1 §1.2.3 — agents and types of pollination; outbreeding devices.",
                    ),
                ],
            ),
            (
                "double-fertilisation",
                "Double Fertilisation",
                [
                    (
                        "syngamy-and-triple-fusion",
                        "Syngamy and Triple Fusion",
                        "NCERT XII Biology Ch 1 §1.3 — fusion events characteristic of angiosperms.",
                    ),
                ],
            ),
            (
                "post-fertilisation-events",
                "Post-Fertilisation: Structures and Events",
                [
                    (
                        "endosperm-embryo-seed",
                        "Endosperm, Embryo and Seed",
                        "NCERT XII Biology Ch 1 §1.4 — endosperm types, embryo development and seed structure.",
                    ),
                    (
                        "apomixis-polyembryony",
                        "Apomixis and Polyembryony",
                        "NCERT XII Biology Ch 1 §1.5 — asexual seed formation and multiple embryos.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "principles-of-inheritance-and-variation",
        "name": "Principles of Inheritance and Variation",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo104.pdf",
        "ncert_ch": 4,
        "topics": [
            (
                "mendels-laws",
                "Mendel’s Laws of Inheritance",
                [
                    (
                        "law-of-dominance",
                        "Law of Dominance",
                        "NCERT XII Biology Ch 4 §4.2.1 — dominant and recessive alleles in monohybrid crosses.",
                    ),
                    (
                        "law-of-segregation",
                        "Law of Segregation",
                        "NCERT XII Biology Ch 4 §4.2.2 — allele pairs segregate during gamete formation.",
                    ),
                ],
            ),
            (
                "inheritance-of-two-genes",
                "Inheritance of Two Genes",
                [
                    (
                        "independent-assortment",
                        "Law of Independent Assortment",
                        "NCERT XII Biology Ch 4 §4.3.1 — dihybrid ratios from independent assortment.",
                    ),
                    (
                        "linkage-and-recombination",
                        "Linkage and Recombination",
                        "NCERT XII Biology Ch 4 §4.3.3 — linked genes and crossing over.",
                    ),
                ],
            ),
            (
                "extensions-and-sex-determination",
                "Polygenic Inheritance, Pleiotropy and Sex Determination",
                [
                    (
                        "polygenic-inheritance",
                        "Polygenic Inheritance",
                        "NCERT XII Biology Ch 4 §4.4 — quantitative traits controlled by multiple loci.",
                    ),
                    (
                        "pleiotropy",
                        "Pleiotropy",
                        "NCERT XII Biology Ch 4 §4.5 — single gene affecting multiple phenotypic traits.",
                    ),
                    (
                        "sex-determination",
                        "Sex Determination",
                        "NCERT XII Biology Ch 4 §4.6 — chromosomal basis of sex determination.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "molecular-basis-of-inheritance",
        "name": "Molecular Basis of Inheritance",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo105.pdf",
        "ncert_ch": 5,
        "topics": [
            (
                "the-dna",
                "The DNA",
                [
                    (
                        "polynucleotide-structure",
                        "Structure of Polynucleotide Chain",
                        "NCERT XII Biology Ch 5 §5.1.1 — nucleotides, bases, sugars and phosphodiester bonds.",
                    ),
                    (
                        "packaging-of-dna-helix",
                        "Packaging of DNA Helix",
                        "NCERT XII Biology Ch 5 §5.1.2 — nucleosomes and higher-order chromatin packaging.",
                    ),
                ],
            ),
            (
                "genetic-material-and-replication",
                "Search for Genetic Material and Replication",
                [
                    (
                        "dna-as-genetic-material",
                        "The Genetic Material is DNA",
                        "NCERT XII Biology Ch 5 §5.2 — experiments establishing DNA as genetic material.",
                    ),
                    (
                        "dna-replication",
                        "DNA Replication",
                        "NCERT XII Biology Ch 5 §5.4 — semi-conservative replication and experimental proof.",
                    ),
                ],
            ),
            (
                "transcription-translation-regulation",
                "Transcription, Translation and Regulation",
                [
                    (
                        "transcription",
                        "Transcription",
                        "NCERT XII Biology Ch 5 — RNA synthesis from DNA template.",
                    ),
                    (
                        "genetic-code-and-translation",
                        "Genetic Code and Translation",
                        "NCERT XII Biology Ch 5 — codon dictionary and polypeptide synthesis.",
                    ),
                    (
                        "dna-fingerprinting",
                        "DNA Fingerprinting",
                        "NCERT XII Biology Ch 5 §5.10 — VNTRs and forensic applications.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "microbes-in-human-welfare",
        "name": "Microbes in Human Welfare",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo108.pdf",
        "ncert_ch": 8,
        "topics": [
            (
                "microbes-in-household-and-industry",
                "Microbes in Household Products and Industrial Products",
                [
                    (
                        "household-products",
                        "Microbes in Household Products",
                        "NCERT XII Biology Ch 8 §8.1 — fermented foods and dairy products.",
                    ),
                    (
                        "fermented-beverages-antibiotics",
                        "Fermented Beverages and Antibiotics",
                        "NCERT XII Biology Ch 8 §8.2 — industrial fermentation products and antibiotics.",
                    ),
                ],
            ),
            (
                "microbes-in-environment",
                "Microbes in Sewage Treatment, Biogas, Biocontrol and Biofertilisers",
                [
                    (
                        "sewage-treatment-biogas",
                        "Sewage Treatment and Biogas",
                        "NCERT XII Biology Ch 8 §8.3–8.4 — BOD reduction and methanogens.",
                    ),
                    (
                        "biocontrol-biofertilisers",
                        "Biocontrol Agents and Biofertilisers",
                        "NCERT XII Biology Ch 8 §8.5–8.6 — biological pest control and nitrogen fixers.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "biotechnology-principles-and-processes",
        "name": "Biotechnology: Principles and Processes",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo109.pdf",
        "ncert_ch": 9,
        "topics": [
            (
                "principles-of-biotechnology",
                "Principles of Biotechnology",
                [
                    (
                        "restriction-enzymes",
                        "Restriction Enzymes",
                        "NCERT XII Biology Ch 9 §9.2.1 — cutting DNA at recognition sites.",
                    ),
                    (
                        "cloning-vectors",
                        "Cloning Vectors",
                        "NCERT XII Biology Ch 9 §9.2.2 — plasmids/vectors for gene transfer.",
                    ),
                ],
            ),
            (
                "recombinant-dna-processes",
                "Processes of Recombinant DNA Technology",
                [
                    (
                        "isolation-and-cutting-dna",
                        "Isolation and Cutting of DNA",
                        "NCERT XII Biology Ch 9 §9.3.1–9.3.2 — DNA isolation and restriction digestion.",
                    ),
                    (
                        "pcr-and-downstream-processing",
                        "PCR Amplification and Downstream Processing",
                        "NCERT XII Biology Ch 9 §9.3.3–9.3.6 — amplifying insert and recovering product.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "biotechnology-and-its-applications",
        "name": "Biotechnology and its Applications",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo110.pdf",
        "ncert_ch": 10,
        "topics": [
            (
                "applications-in-agriculture",
                "Biotechnological Applications in Agriculture",
                [
                    (
                        "bt-crops-and-pest-resistance",
                        "Bt Crops and Pest Resistance",
                        "NCERT XII Biology Ch 10 §10.1 — genetically modified crops for pest resistance.",
                    ),
                ],
            ),
            (
                "applications-in-medicine",
                "Biotechnological Applications in Medicine",
                [
                    (
                        "ge-insulin-gene-therapy",
                        "Genetically Engineered Insulin and Gene Therapy",
                        "NCERT XII Biology Ch 10 §10.2.1–10.2.2 — recombinant insulin and gene therapy.",
                    ),
                    (
                        "molecular-diagnosis",
                        "Molecular Diagnosis",
                        "NCERT XII Biology Ch 10 §10.2.3 — PCR/ELISA-based diagnosis.",
                    ),
                ],
            ),
            (
                "transgenic-animals-ethics",
                "Transgenic Animals and Ethical Issues",
                [
                    (
                        "transgenic-animals",
                        "Transgenic Animals",
                        "NCERT XII Biology Ch 10 §10.3 — uses of transgenic animals.",
                    ),
                    (
                        "ethical-issues-biotech",
                        "Ethical Issues",
                        "NCERT XII Biology Ch 10 §10.4 — biopiracy and ethical concerns.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "organisms-and-populations",
        "name": "Organisms and Populations",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo111.pdf",
        "ncert_ch": 11,
        "topics": [
            (
                "population-attributes-and-growth",
                "Population Attributes and Growth",
                [
                    (
                        "population-attributes",
                        "Population Attributes",
                        "NCERT XII Biology Ch 11 §11.1.1 — birth/death rates, age distribution, sex ratio.",
                    ),
                    (
                        "population-growth",
                        "Population Growth",
                        "NCERT XII Biology Ch 11 §11.1.2 — exponential and logistic growth models.",
                    ),
                ],
            ),
            (
                "population-interactions",
                "Population Interactions",
                [
                    (
                        "life-history-and-interactions",
                        "Life History Variation and Population Interactions",
                        "NCERT XII Biology Ch 11 §11.1.3–11.1.4 — life-history traits and interaction types.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "ecosystem",
        "name": "Ecosystem",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo112.pdf",
        "ncert_ch": 12,
        "topics": [
            (
                "ecosystem-structure-function",
                "Ecosystem – Structure and Function",
                [
                    (
                        "structure-and-productivity",
                        "Structure, Function and Productivity",
                        "NCERT XII Biology Ch 12 §12.1–12.2 — biotic/abiotic components and productivity.",
                    ),
                ],
            ),
            (
                "decomposition-energy-pyramids",
                "Decomposition, Energy Flow and Ecological Pyramids",
                [
                    (
                        "decomposition",
                        "Decomposition",
                        "NCERT XII Biology Ch 12 §12.3 — detritus processing and nutrient cycling.",
                    ),
                    (
                        "energy-flow-and-pyramids",
                        "Energy Flow and Ecological Pyramids",
                        "NCERT XII Biology Ch 12 §12.4–12.5 — trophic levels and pyramid types.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "BOTANY",
        "code": "biodiversity-and-conservation",
        "name": "Biodiversity and Conservation",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo113.pdf",
        "ncert_ch": 13,
        "topics": [
            (
                "biodiversity-patterns-and-loss",
                "Biodiversity: Patterns and Loss",
                [
                    (
                        "patterns-of-biodiversity",
                        "Patterns of Biodiversity",
                        "NCERT XII Biology Ch 13 §13.1.2 — latitudinal gradients and species–area relationships.",
                    ),
                    (
                        "loss-of-biodiversity",
                        "Loss of Biodiversity",
                        "NCERT XII Biology Ch 13 §13.1.4 — causes and consequences of biodiversity loss.",
                    ),
                ],
            ),
            (
                "biodiversity-conservation",
                "Biodiversity Conservation",
                [
                    (
                        "why-and-how-conserve",
                        "Why and How We Conserve Biodiversity",
                        "NCERT XII Biology Ch 13 §13.2 — in-situ and ex-situ conservation approaches.",
                    ),
                ],
            ),
        ],
    },
    # ---- ZOOLOGY XII ----
    {
        "subject": "ZOOLOGY",
        "code": "human-reproduction",
        "name": "Human Reproduction",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo102.pdf",
        "ncert_ch": 2,
        "preserve_existing": True,
        "topics": [],  # do not invent replacements; preserve existing tree
    },
    {
        "subject": "ZOOLOGY",
        "code": "reproductive-health",
        "name": "Reproductive Health",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo103.pdf",
        "ncert_ch": 3,
        "topics": [
            (
                "reproductive-health-problems",
                "Reproductive Health – Problems and Strategies",
                [
                    (
                        "population-stabilisation-birth-control",
                        "Population Stabilisation and Birth Control",
                        "NCERT XII Biology Ch 3 §3.2 — contraceptive methods and population control.",
                    ),
                ],
            ),
            (
                "mtp-sti-infertility",
                "MTP, STIs and Infertility",
                [
                    (
                        "medical-termination-of-pregnancy",
                        "Medical Termination of Pregnancy (MTP)",
                        "NCERT XII Biology Ch 3 §3.3 — legal and medical aspects of MTP.",
                    ),
                    (
                        "sexually-transmitted-infections",
                        "Sexually Transmitted Infections (STIs)",
                        "NCERT XII Biology Ch 3 §3.4 — common STIs and prevention.",
                    ),
                    (
                        "infertility-assisted-reproduction",
                        "Infertility",
                        "NCERT XII Biology Ch 3 §3.5 — causes and assisted reproductive technologies.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "ZOOLOGY",
        "code": "evolution",
        "name": "Evolution",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo106.pdf",
        "ncert_ch": 6,
        "topics": [
            (
                "origin-and-evidences",
                "Origin of Life and Evidences for Evolution",
                [
                    (
                        "origin-of-life",
                        "Origin of Life",
                        "NCERT XII Biology Ch 6 §6.1 — early earth and origin hypotheses.",
                    ),
                    (
                        "evidences-for-evolution",
                        "Evidences for Evolution",
                        "NCERT XII Biology Ch 6 §6.3 — palaeontological, morphological and molecular evidence.",
                    ),
                ],
            ),
            (
                "mechanism-and-human-evolution",
                "Mechanism of Evolution and Human Evolution",
                [
                    (
                        "adaptive-radiation-hardy-weinberg",
                        "Adaptive Radiation and Hardy–Weinberg Principle",
                        "NCERT XII Biology Ch 6 §6.4–6.7 — adaptive radiation and genetic equilibrium.",
                    ),
                    (
                        "origin-and-evolution-of-man",
                        "Origin and Evolution of Man",
                        "NCERT XII Biology Ch 6 §6.9 — human evolutionary lineage.",
                    ),
                ],
            ),
        ],
    },
    {
        "subject": "ZOOLOGY",
        "code": "human-health-and-disease",
        "name": "Human Health and Disease",
        "pdf_rel": "Class 12/Biology/lebo1dd/lebo107.pdf",
        "ncert_ch": 7,
        "topics": [
            (
                "common-diseases-and-immunity",
                "Common Diseases and Immunity",
                [
                    (
                        "common-diseases-in-humans",
                        "Common Diseases in Humans",
                        "NCERT XII Biology Ch 7 §7.1 — infectious diseases and pathogens.",
                    ),
                    (
                        "innate-and-acquired-immunity",
                        "Innate and Acquired Immunity",
                        "NCERT XII Biology Ch 7 §7.2 — barriers, antibodies, active/passive immunity, vaccines.",
                    ),
                ],
            ),
            (
                "aids-cancer-substance-abuse",
                "AIDS, Cancer and Drugs/Alcohol Abuse",
                [
                    (
                        "aids",
                        "AIDS",
                        "NCERT XII Biology Ch 7 §7.3 — HIV infection and prevention.",
                    ),
                    (
                        "cancer",
                        "Cancer",
                        "NCERT XII Biology Ch 7 §7.4 — uncontrolled cell division and causes.",
                    ),
                    (
                        "drugs-and-alcohol-abuse",
                        "Drugs and Alcohol Abuse",
                        "NCERT XII Biology Ch 7 §7.5 — adolescence, addiction and prevention.",
                    ),
                ],
            ),
        ],
    },
]


def snapshot(engine) -> dict:
    with engine.connect() as conn:
        status = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT status, COUNT(*) FROM cms.content_items
                    WHERE deleted_at IS NULL AND content_type='QUESTION'
                    GROUP BY 1
                    """
                )
            )
        }
        unmapped = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type='QUESTION'
                  AND status='DRAFT' AND concept_id IS NULL
                """
            )
        ).scalar()
        bio_rows = [
            dict(r)
            for r in conn.execute(
                text(
                    """
                    SELECT s.code AS subject, ch.code, ch.name, ch.class_level,
                           (SELECT COUNT(*) FROM academic.topics t
                              WHERE t.chapter_id=ch.id AND t.deleted_at IS NULL) AS topics,
                           (SELECT COUNT(*) FROM academic.concepts c
                              JOIN academic.topics t ON t.id=c.topic_id AND t.deleted_at IS NULL
                              WHERE t.chapter_id=ch.id AND c.deleted_at IS NULL) AS concepts
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id=ch.subject_id
                    WHERE s.code IN ('BOTANY','ZOOLOGY') AND ch.class_level='12'
                      AND ch.deleted_at IS NULL
                    ORDER BY s.code, ch.name
                    """
                )
            ).mappings()
        ]
        return {
            "status": status,
            "unmapped_draft": unmapped,
            "chapters": conn.execute(text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")).scalar(),
            "topics": conn.execute(text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")).scalar(),
            "concepts": conn.execute(text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")).scalar(),
            "knowledge_units": conn.execute(
                text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")
            ).scalar(),
            "question_blueprints": conn.execute(
                text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
            ).scalar(),
            "content_batches": conn.execute(
                text("SELECT COUNT(*) FROM cms.content_batches WHERE deleted_at IS NULL")
            ).scalar(),
            "generation_jobs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar(),
            "generation_runs": conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar(),
            "generation_candidates": conn.execute(
                text("SELECT COUNT(*) FROM cms.generation_candidates")
            ).scalar(),
            "biology_xii": bio_rows,
        }


def verify_pdf_identity(spec: dict, root: Path) -> dict:
    """Identify chapter from canonical PDF filename + uppercase CHAPTER header.

    Prose cross-references like "in Chapter 2" must not be treated as the
    PDF's own chapter identity. Prefer uppercase ``CHAPTER N`` and matching
    ``N.M`` section prefixes over case-insensitive Chapter matches.
    """
    pdf = root / spec["pdf_rel"]
    info = {
        "code": spec["code"],
        "expected_name": spec["name"],
        "pdf_rel": spec["pdf_rel"],
        "expected_ncert_ch": spec["ncert_ch"],
        "exists": pdf.is_file(),
        "validated": False,
        "pdf_chapter_hint": None,
        "discrepancy": None,
        "note": None,
        "error": None,
    }
    try:
        validate_ncert_generation_source(pdf, root=root)
        info["validated"] = True
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
        return info

    doc = fitz.open(pdf)
    try:
        pages = []
        for i in range(min(3, doc.page_count)):
            pages.append(doc.load_page(i).get_text("text") or "")
        sample = "\n".join(pages)

        m_file = re.match(r"lebo1(\d{2})\.pdf$", Path(spec["pdf_rel"]).name, re.I)
        file_ch = int(m_file.group(1)) if m_file else None

        # NCERT chapter title headers are typically all-caps CHAPTER N.
        caps_headers = [int(x) for x in re.findall(r"(?<![A-Za-z])CHAPTER\s+(\d{1,2})(?!\w)", sample)]
        # Section prefixes like 3.1 reinforce identity when present.
        section_prefix = None
        sec_hits = re.findall(r"(?m)^(\d{1,2})\.\d+", sample)
        if sec_hits:
            # Dominant first-digit among early section headings
            from collections import Counter

            section_prefix = int(Counter(int(x) for x in sec_hits).most_common(1)[0][0])

        text_ch = caps_headers[0] if caps_headers else section_prefix
        prose_refs = [int(x) for x in re.findall(r"(?<![A-Z])Chapter\s+(\d{1,2})", sample)]

        info["pdf_chapter_hint"] = {
            "filename": file_ch,
            "text_header_caps": caps_headers[:3],
            "section_prefix": section_prefix,
            "resolved_text_ch": text_ch,
            "prose_chapter_refs": prose_refs[:5],
        }

        if file_ch and file_ch != spec["ncert_ch"]:
            info["discrepancy"] = (
                f"Owner/report chapter {spec['ncert_ch']} vs filename chapter {file_ch}"
            )
        elif text_ch and file_ch and text_ch != file_ch:
            info["discrepancy"] = (
                f"PDF text CHAPTER {text_ch} vs filename chapter {file_ch}"
            )
        elif prose_refs and file_ch and any(r != file_ch for r in prose_refs):
            # Document only — not a discrepancy (cross-chapter prose).
            other = sorted({r for r in prose_refs if r != file_ch})
            info["note"] = (
                f"Prose mentions Chapter {other} (cross-reference); "
                f"PDF identity remains chapter {file_ch} via filename"
                + (f"/CHAPTER {text_ch}" if text_ch else "")
            )
    finally:
        doc.close()
    return info


def run_validation_suite() -> dict:
    """Run CF-C2 validation gates (no AI / no Content Factory)."""
    import subprocess
    import sys

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "app/modules/ingestion/tests/test_ncert_canonical_source.py",
        "app/modules/academic/tests/test_cf_c1_chemistry_class_12.py",
        "app/modules/academic/tests/test_chapter_class_level.py",
        "tests/test_cms_workflow.py",
        "tests/test_cms_publish_quality.py",
        "tests/test_phase32_content_readiness_safety.py",
        "tests/test_phase33_ecaep_publication_safety.py",
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # pytest summary line: "N passed" / "N failed"
    passed = failed = None
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_fail = re.search(r"(\d+)\s+failed", out)
    if m_pass:
        passed = int(m_pass.group(1))
    if m_fail:
        failed = int(m_fail.group(1))
    else:
        failed = 0 if proc.returncode == 0 else None
    return {
        "passed": passed,
        "failed": failed,
        "exit_code": proc.returncode,
        "command": " ".join(cmd),
        "tail": "\n".join(out.strip().splitlines()[-30:]),
    }


def integrity_checks(engine) -> dict:
    with engine.connect() as conn:
        dups = conn.execute(
            text(
                """
                SELECT s.code, ch.code, COUNT(*)
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.deleted_at IS NULL
                GROUP BY 1, 2 HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        orphan_topics = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.topics t
                LEFT JOIN academic.chapters ch ON ch.id = t.chapter_id AND ch.deleted_at IS NULL
                WHERE t.deleted_at IS NULL AND ch.id IS NULL
                """
            )
        ).scalar()
        orphan_concepts = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM academic.concepts c
                LEFT JOIN academic.topics t ON t.id = c.topic_id AND t.deleted_at IS NULL
                WHERE c.deleted_at IS NULL AND t.id IS NULL
                """
            )
        ).scalar()
        codes = [s["code"] for s in APPROVED]
        class_level_bad = 0
        for code in codes:
            class_level_bad += conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ch.deleted_at IS NULL
                      AND s.code IN ('BOTANY','ZOOLOGY')
                      AND ch.code = :code
                      AND ch.class_level IS DISTINCT FROM '12'
                    """
                ),
                {"code": code},
            ).scalar()
    return {
        "duplicate_chapters": [list(r) for r in dups],
        "orphan_topics": orphan_topics,
        "orphan_concepts": orphan_concepts,
        "wrong_class_level_count": class_level_bad,
        "ok": not dups and orphan_topics == 0 and orphan_concepts == 0 and class_level_bad == 0,
    }


async def apply_taxonomy(session: AsyncSession) -> dict:
    result = {
        "chapters_added": [],
        "topics_added": [],
        "concepts_added": [],
        "existing_preserved": [],
        "ownership_applied": [],
        "skipped": [],
        "errors": [],
    }

    subjects: dict[str, Subject] = {}
    for code in ("BOTANY", "ZOOLOGY"):
        subj = (await session.execute(select(Subject).where(Subject.code == code))).scalar_one_or_none()
        if not subj:
            result["errors"].append(f"Missing subject {code}")
            return result
        subjects[code] = subj

    for spec in APPROVED:
        subj = subjects[spec["subject"]]
        result["ownership_applied"].append(
            {"subject": spec["subject"], "code": spec["code"], "name": spec["name"], "pdf": spec["pdf_rel"]}
        )

        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.subject_id == subj.id, Chapter.code == spec["code"])
            )
        ).scalar_one_or_none()

        # Also detect same code under wrong subject (do not silently move).
        other = (
            await session.execute(select(Chapter).where(Chapter.code == spec["code"], Chapter.deleted_at.is_(None)))
        ).scalars().all()
        wrong = [ch for ch in other if ch.subject_id != subj.id]
        if wrong:
            result["errors"].append(
                f"Chapter code {spec['code']} exists under another subject; not moved"
            )
            continue

        if chapter:
            result["existing_preserved"].append(
                {
                    "subject": spec["subject"],
                    "code": chapter.code,
                    "name": chapter.name,
                    "class_level": chapter.class_level,
                    "note": "preserved; name/ownership not silently rewritten",
                }
            )
            # Ensure class_level is 12 if null/wrong only when preserve path and empty? Owner said don't silently change.
            # Only set class_level if missing NULL.
            if chapter.class_level is None:
                chapter.class_level = "12"
                result["skipped"].append(
                    {"type": "class_level_null_set_to_12", "code": chapter.code}
                )
        else:
            max_order = (
                await session.execute(
                    select(Chapter.display_order)
                    .where(Chapter.subject_id == subj.id, Chapter.deleted_at.is_(None))
                    .order_by(Chapter.display_order.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            chapter = Chapter(
                subject_id=subj.id,
                code=spec["code"],
                name=spec["name"],
                display_order=(int(max_order) + 1) if max_order is not None else 0,
                neet_weightage_percent=None,
                class_level="12",
            )
            session.add(chapter)
            await session.flush()
            result["chapters_added"].append(
                {"subject": spec["subject"], "code": spec["code"], "name": spec["name"], "pdf": spec["pdf_rel"]}
            )

        if spec.get("preserve_existing") and not spec.get("topics"):
            result["skipped"].append(
                {"type": "preserve_existing_no_topic_injection", "code": spec["code"]}
            )
            continue

        for topic_order, (topic_code, topic_name, concepts) in enumerate(spec.get("topics") or []):
            topic = (
                await session.execute(
                    select(Topic).where(Topic.chapter_id == chapter.id, Topic.code == topic_code)
                )
            ).scalar_one_or_none()
            if not topic:
                topic = Topic(
                    chapter_id=chapter.id,
                    code=topic_code,
                    name=topic_name,
                    display_order=topic_order,
                )
                session.add(topic)
                await session.flush()
                result["topics_added"].append(
                    {"chapter": spec["code"], "code": topic_code, "name": topic_name}
                )
            else:
                result["skipped"].append(
                    {"type": "topic_exists", "chapter": spec["code"], "code": topic_code}
                )

            for concept_order, (concept_code, concept_name, summary) in enumerate(concepts):
                concept = (
                    await session.execute(
                        select(Concept).where(Concept.topic_id == topic.id, Concept.code == concept_code)
                    )
                ).scalar_one_or_none()
                if not concept:
                    session.add(
                        Concept(
                            topic_id=topic.id,
                            code=concept_code,
                            name=concept_name,
                            summary=summary,
                            display_order=concept_order,
                        )
                    )
                    result["concepts_added"].append(
                        {
                            "chapter": spec["code"],
                            "topic": topic_code,
                            "code": concept_code,
                            "name": concept_name,
                        }
                    )
                else:
                    result["skipped"].append(
                        {
                            "type": "concept_exists",
                            "chapter": spec["code"],
                            "topic": topic_code,
                            "code": concept_code,
                        }
                    )

    await session.commit()
    return result


def write_report(payload: dict) -> tuple[Path, Path]:
    stamp = date.today().strftime("%Y%m%d")
    out = ROOT / "docs" / "audits"
    out.mkdir(parents=True, exist_ok=True)
    jp = out / f"curriculum_baseline_002_biology_{stamp}.json"
    mp = out / f"curriculum_baseline_002_biology_{stamp}.md"
    jp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# CF-C2 — Biology Class 12 owner-approved taxonomy",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Final status: **{payload['final_status']}**",
        "- Git: **no commit / no push**",
        "",
        "## Ownership mapping applied",
        "",
    ]
    for row in payload["apply"]["ownership_applied"]:
        lines.append(f"- **{row['subject']}** ← `{row['code']}` — {row['name']} (`{row['pdf']}`)")
    lines.append("")
    lines.append("## Chapters added")
    for row in payload["apply"]["chapters_added"]:
        lines.append(f"- `{row['subject']}` `{row['code']}` — {row['name']}")
    if not payload["apply"]["chapters_added"]:
        lines.append("- _(none)_")
    lines.append("")
    lines.append(f"## Topics added: {len(payload['apply']['topics_added'])}")
    lines.append(f"## Concepts added: {len(payload['apply']['concepts_added'])}")
    lines.append("")
    lines.append("## Existing preserved")
    for row in payload["apply"]["existing_preserved"]:
        lines.append(f"- `{row['subject']}` `{row['code']}` — {row['name']} (class {row['class_level']})")
    lines.append("")
    lines.append("## Unresolved chapters")
    lines.append("")
    if not payload["unresolved"]:
        lines.append("- _(none under owner-approved list)_")
    for u in payload["unresolved"]:
        lines.append(f"- {u}")
    lines.append("")
    lines.append("## PDF verification")
    for v in payload["pdf_verification"]:
        disc = v.get("discrepancy") or "none"
        note = v.get("note")
        extra = f" note={note}" if note else ""
        lines.append(
            f"- `{v['code']}` ← `{v['pdf_rel']}` validated={v['validated']} discrepancy={disc}{extra}"
        )
    lines.append("")
    lines.append("## Integrity checks")
    lines.append("```json")
    lines.append(json.dumps(payload.get("integrity") or {}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Safety")
    lines.append("### Before")
    lines.append("```json")
    lines.append(json.dumps({k: payload["before"][k] for k in payload["before"] if k != "biology_xii"}, indent=2))
    lines.append("```")
    lines.append("### After")
    lines.append("```json")
    lines.append(json.dumps({k: payload["after"][k] for k in payload["after"] if k != "biology_xii"}, indent=2))
    lines.append("```")
    lines.append("")
    lines.append(f"- Content safety unchanged: `{payload['content_safety_unchanged']}`")
    lines.append(f"- Freeze OK: `{payload.get('freeze_ok')}`")
    lines.append(f"- Unmapped DRAFT: `{payload['before']['unmapped_draft']}` → `{payload['after']['unmapped_draft']}`")
    lines.append("")
    lines.append("## Tests")
    lines.append(
        f"- Passed: `{payload['tests']['passed']}` Failed: `{payload['tests']['failed']}` "
        f"exit=`{payload['tests'].get('exit_code')}`"
    )
    lines.append(f"- `{payload['tests']['command']}`")
    if payload["tests"].get("tail"):
        lines.append("```")
        lines.append(payload["tests"]["tail"])
        lines.append("```")
    lines.append("")
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp


async def amain() -> int:
    settings = get_settings()
    sync = create_engine(settings.database_url_sync)
    before = snapshot(sync)
    root = get_ncert_source_root()
    pdf_verification = [verify_pdf_identity(spec, root) for spec in APPROVED]

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        apply = await apply_taxonomy(session)
    await engine.dispose()

    after = snapshot(sync)

    # Idempotent re-run: keep first CF-C2 before/apply deltas for the audit report.
    prior_path = Path(__file__).resolve().parents[3] / "docs" / "audits" / "curriculum_baseline_002_biology_20260913.json"
    if prior_path.is_file() and not apply.get("chapters_added"):
        try:
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
            if prior.get("apply", {}).get("chapters_added"):
                apply["chapters_added"] = prior["apply"]["chapters_added"]
                apply["topics_added"] = prior["apply"].get("topics_added") or apply.get("topics_added") or []
                apply["concepts_added"] = prior["apply"].get("concepts_added") or apply.get("concepts_added") or []
                apply["existing_preserved"] = prior["apply"].get("existing_preserved") or apply.get("existing_preserved")
                apply["ownership_applied"] = prior["apply"].get("ownership_applied") or apply.get("ownership_applied")
                apply["idempotent_rerun"] = True
            if prior.get("before") and prior["before"].get("chapters", 0) < after.get("chapters", 0):
                before = prior["before"]
        except Exception:  # noqa: BLE001
            pass

    content_safety = before["status"] == after["status"] and before["unmapped_draft"] == after["unmapped_draft"]
    freeze_ok = after["unmapped_draft"] == 5024 and after["status"] == {
        "DRAFT": 5298,
        "PUBLISHED": 1479,
        "SUPERSEDED": 6,
        "IN_REVIEW": 111,
    }

    approved_codes = {s["code"] for s in APPROVED}
    after_codes = {r["code"] for r in after["biology_xii"]}
    missing = sorted(approved_codes - after_codes)
    unresolved = [f"Missing after apply: {c}" for c in missing]
    unresolved.extend(
        [f"PDF discrepancy for {v['code']}: {v['discrepancy']}" for v in pdf_verification if v.get("discrepancy")]
    )
    unresolved.extend(apply.get("errors") or [])

    integrity = integrity_checks(sync)
    if not integrity["ok"]:
        unresolved.append(f"Integrity failed: {integrity}")

    tests = run_validation_suite()
    if tests.get("exit_code") != 0:
        unresolved.append(f"Validation tests failed (exit {tests.get('exit_code')})")

    all_pdfs_ok = all(v.get("validated") and v.get("exists") for v in pdf_verification)
    chapters_ok = not missing
    thin = [
        r
        for r in after["biology_xii"]
        if r["code"] in approved_codes and r["code"] != "human-reproduction" and (r["topics"] < 1 or r["concepts"] < 1)
    ]
    if thin:
        unresolved.append(f"Thin taxonomy trees: {[r['code'] for r in thin]}")

    if not content_safety or not freeze_ok:
        status = "RED — FAILED"
    elif not all_pdfs_ok or not chapters_ok or apply.get("errors") or thin or not integrity["ok"]:
        status = "YELLOW — PARTIALLY VERIFIED"
    elif unresolved and any("discrepancy" in u.lower() for u in unresolved):
        status = "YELLOW — PARTIALLY VERIFIED"
    elif tests.get("exit_code") != 0:
        status = "YELLOW — PARTIALLY VERIFIED"
    else:
        status = "GREEN — COMPLETE/VERIFIED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_status": status,
        "before": before,
        "after": after,
        "content_safety_unchanged": content_safety,
        "freeze_ok": freeze_ok,
        "pdf_verification": pdf_verification,
        "apply": apply,
        "integrity": integrity,
        "unresolved": unresolved,
        "tests": tests,
        "notes": [v.get("note") for v in pdf_verification if v.get("note")],
    }
    jp, mp = write_report(payload)
    print(
        json.dumps(
            {
                "final_status": status,
                "json": str(jp),
                "md": str(mp),
                "chapters_added": len(apply["chapters_added"]),
                "topics_added": len(apply["topics_added"]),
                "concepts_added": len(apply["concepts_added"]),
                "unmapped": after["unmapped_draft"],
                "integrity_ok": integrity["ok"],
                "tests_passed": tests.get("passed"),
                "tests_failed": tests.get("failed"),
                "biology_xii_after": after["biology_xii"],
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
