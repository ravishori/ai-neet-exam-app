"""RS-003-B-1: academic.chapters.class_level (NCERT Class 11/12 taxonomy)

Revision ID: rs003b1_chapter_cls
Revises: e1f2a3b4c5d6
Create Date: 2026-09-08 21:00:00.000000

Adds a nullable NCERT class column to academic.chapters and backfills the
34 chapter codes whose class assignment is verified in RS-003-B-1A. The
column remains NULLABLE by design: ZOOLOGY 'biomolecules' is intentionally
unresolved (see the RS-003-B-1A audit) and MUST NOT receive a value here.

Does NOT modify:
  - any content_items / content_versions / question bodies
  - any body.ncert_evidence
  - any topic / concept / question row
  - any other chapter metadata (name / subject_id / display_order /
    weightage / topics)
  - the Botany/Zoology subject split
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "rs003b1_chapter_cls"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


CLASS_11 = {
    "PHYSICS": (
        "units-and-measurement",
        "kinematics",
        "laws-of-motion",
        "work-energy-power",
        "systems-of-particles-rotational-motion",
        "gravitation",
        "mechanical-properties-of-solids",
        "mechanical-properties-of-fluids",
        "thermodynamics-physics",
        "kinetic-theory",
    ),
    "CHEMISTRY": (
        "basic-concepts-chemistry",
        "structure-of-atom",
        "chemical-bonding",
        "thermodynamics-chemistry",
        "equilibrium",
        "redox-reactions",
        "organic-chemistry-basics",
    ),
    "BOTANY": (
        "the-living-world",
        "plant-kingdom",
        "morphology-flowering-plants",
        "cell-unit-of-life",
        "photosynthesis",
        "plant-growth-development",
    ),
    "ZOOLOGY": (
        "animal-kingdom",
        "structural-organisation-animals",
        "digestion-absorption",
        "breathing-exchange-of-gases",
        "body-fluids-circulation",
    ),
}

CLASS_12 = {
    "PHYSICS": ("electrostatics", "current-electricity", "optics"),
    "CHEMISTRY": ("electrochemistry",),
    "BOTANY": ("sexual-reproduction-flowering-plants",),
    "ZOOLOGY": ("human-reproduction",),
}


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column("class_level", sa.String(length=2), nullable=True),
        schema="academic",
    )
    op.create_check_constraint(
        "ck_chapters_class_level_allowed",
        "chapters",
        "class_level IS NULL OR class_level IN ('11', '12')",
        schema="academic",
    )

    conn = op.get_bind()
    for cls, per_subject in (("11", CLASS_11), ("12", CLASS_12)):
        for subject_code, chapter_codes in per_subject.items():
            for chapter_code in chapter_codes:
                conn.execute(
                    sa.text(
                        """
                        UPDATE academic.chapters
                        SET class_level = :cls
                        WHERE code = :code
                          AND subject_id = (
                              SELECT id FROM academic.subjects WHERE code = :subj
                          )
                        """
                    ),
                    {"cls": cls, "code": chapter_code, "subj": subject_code},
                )


def downgrade() -> None:
    op.drop_constraint(
        "ck_chapters_class_level_allowed",
        "chapters",
        type_="check",
        schema="academic",
    )
    op.drop_column("chapters", "class_level", schema="academic")
