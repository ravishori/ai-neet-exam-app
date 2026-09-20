"""Batch A academic hierarchy fill — topics/concepts for empty P0 chapters.

Coverage plan (`NEET_CONTENT_COVERAGE_PLAN.md`) requires mapping nodes before
acquisition. Chapters already exist in academic seed; only topics/concepts
are added (idempotent by code). Does not invent new chapter names.
"""

from __future__ import annotations

# chapter_code -> list of (topic_code, topic_name, [(concept_code, concept_name, summary)])
BATCH_A_HIERARCHY: dict[str, list[tuple[str, str, list[tuple[str, str, str]]]]] = {
    "electrostatics": [
        (
            "coulombs-law",
            "Electric Charge and Coulomb's Law",
            [
                (
                    "coulomb-force",
                    "Coulomb's Law",
                    "Force between two point charges is proportional to product of charges and inversely to square of separation.",
                ),
            ],
        ),
        (
            "electric-field-potential",
            "Electric Field and Potential",
            [
                (
                    "field-potential-relation",
                    "Electric Field and Potential",
                    "Electric field is related to the negative gradient of electric potential.",
                ),
            ],
        ),
        (
            "capacitance",
            "Capacitance",
            [
                (
                    "parallel-plate-capacitor",
                    "Parallel Plate Capacitor",
                    "Capacitance of a parallel plate capacitor depends on plate area, separation, and dielectric.",
                ),
            ],
        ),
    ],
    "optics": [
        (
            "reflection-mirrors",
            "Reflection and Mirrors",
            [
                (
                    "mirror-formula",
                    "Spherical Mirror Formula",
                    "Relation between object distance, image distance, and focal length for spherical mirrors.",
                ),
                (
                    # WAVE-P0-11A — required for PHY-02 principal-focus / parallel-ray mapping
                    "principal-focus-spherical-mirror",
                    "Principal Focus of Spherical Mirror",
                    "Paraxial rays parallel to the principal axis meet at the principal focus after reflection from a spherical mirror.",
                ),
            ],
        ),
        (
            "refraction-lenses",
            "Refraction and Lenses",
            [
                (
                    "lens-formula",
                    "Thin Lens Formula",
                    "Relation between object/image distances and focal length for thin lenses.",
                ),
                (
                    # WAVE-P0-11A — required for PHY-08; must not use Thin Lens Formula for n = c/v
                    "refractive-index",
                    "Refractive Index",
                    "Absolute refractive index n = c/v relates speed of light in vacuum to speed in the medium.",
                ),
                (
                    # WAVE-P0-11A — required for PHY-10 lens power / P = 1/f mapping
                    "lens-power-focal-length",
                    "Lens Power and Focal Length",
                    "Lens power in dioptres is P = 1/f with f in metres; sign indicates converging or diverging behaviour.",
                ),
            ],
        ),
        (
            "wave-optics-basics",
            "Wave Optics Basics",
            [
                (
                    "interference-young",
                    "Young's Double Slit",
                    "Interference fringe spacing depends on wavelength, slit separation, and screen distance.",
                ),
            ],
        ),
    ],
    "equilibrium": [
        (
            "chemical-equilibrium",
            "Chemical Equilibrium",
            [
                (
                    "equilibrium-constant",
                    "Equilibrium Constant Kc/Kp",
                    "Ratio of product and reactant concentrations/pressures at equilibrium for a given reaction.",
                ),
            ],
        ),
        (
            "ionic-equilibrium",
            "Ionic Equilibrium and pH",
            [
                (
                    "ph-and-kw",
                    "pH and Ionic Product of Water",
                    "pH = −log[H+]; Kw relates [H+] and [OH−] in aqueous solution.",
                ),
            ],
        ),
        (
            "solubility-product",
            "Solubility Product",
            [
                (
                    "ksp-basics",
                    "Solubility Product Ksp",
                    "Product of ion concentrations in a saturated solution of a sparingly soluble salt.",
                ),
            ],
        ),
    ],
    "organic-chemistry-basics": [
        (
            "iupac-homologous",
            "IUPAC and Homologous Series",
            [
                (
                    "homologous-series",
                    "Homologous Series",
                    "Family of compounds differing by CH2 with similar chemical properties.",
                ),
            ],
        ),
        (
            "electronic-effects",
            "Electronic Effects",
            [
                (
                    "inductive-mesomeric",
                    "Inductive and Resonance Effects",
                    "Electron displacement effects that influence acidity, basicity, and reactivity.",
                ),
            ],
        ),
        (
            "isomerism-intermediates",
            "Isomerism and Intermediates",
            [
                (
                    "structural-isomerism",
                    "Structural Isomerism",
                    "Compounds with same molecular formula but different connectivity.",
                ),
            ],
        ),
    ],
    "cell-unit-of-life": [
        (
            "cell-theory-types",
            "Cell Theory and Cell Types",
            [
                (
                    "prokaryote-eukaryote",
                    "Prokaryotic vs Eukaryotic Cells",
                    "Key structural differences including nucleus and membrane-bound organelles.",
                ),
            ],
        ),
        (
            "cell-organelles",
            "Cell Organelles",
            [
                (
                    "mitochondria-chloroplast",
                    "Mitochondria and Chloroplast",
                    "Double-membrane organelles involved in energy conversion; endosymbiotic features.",
                ),
            ],
        ),
        (
            "membrane-cell-cycle",
            "Membrane and Cell Cycle",
            [
                (
                    "fluid-mosaic",
                    "Fluid Mosaic Model",
                    "Plasma membrane as a fluid bilayer with embedded proteins (Singer–Nicolson).",
                ),
            ],
        ),
    ],
    "animal-kingdom": [
        (
            "classification-basis",
            "Basis of Classification",
            [
                (
                    "levels-of-organisation",
                    "Levels of Organisation",
                    "Cellular, tissue, organ, and organ-system grades used in animal classification.",
                ),
            ],
        ),
        (
            "non-chordates",
            "Non-chordate Phyla",
            [
                (
                    "porifera-cnidaria",
                    "Porifera and Cnidaria",
                    "Diagnostic features such as canal system (Porifera) and cnidocytes (Cnidaria).",
                ),
            ],
        ),
        (
            "chordata-basics",
            "Chordata Basics",
            [
                (
                    "chordate-features",
                    "Fundamental Chordate Features",
                    "Notochord, dorsal hollow nerve cord, pharyngeal slits, and post-anal tail.",
                ),
            ],
        ),
    ],
    "biomolecules": [
        (
            "proteins-enzymes",
            "Proteins and Enzymes",
            [
                (
                    "enzyme-basics",
                    "Enzyme Action",
                    "Enzymes are biological catalysts; activity depends on temperature, pH, and substrate.",
                ),
            ],
        ),
        (
            "carbs-lipids",
            "Carbohydrates and Lipids",
            [
                (
                    "biomolecule-classes",
                    "Major Biomolecule Classes",
                    "Carbohydrates, proteins, lipids, and nucleic acids as primary biomolecules.",
                ),
            ],
        ),
        (
            "nucleic-acids",
            "Nucleic Acids",
            [
                (
                    "dna-rna",
                    "DNA and RNA",
                    "DNA stores genetic information; RNA participates in protein synthesis.",
                ),
            ],
        ),
    ],
    "human-reproduction": [
        (
            "reproductive-systems",
            "Male and Female Reproductive Systems",
            [
                (
                    "gonads-ducts",
                    "Gonads and Ducts",
                    "Primary sex organs produce gametes; ducts transport and support reproductive function.",
                ),
            ],
        ),
        (
            "gametogenesis",
            "Gametogenesis",
            [
                (
                    "spermatogenesis-oogenesis",
                    "Spermatogenesis and Oogenesis",
                    "Formation of spermatozoa and ova through meiosis with distinct timelines.",
                ),
            ],
        ),
        (
            "cycle-fertilization",
            "Menstrual Cycle and Fertilization",
            [
                (
                    "menstrual-phases",
                    "Menstrual Cycle Phases",
                    "Follicular, ovulatory, and luteal phases regulated by FSH, LH, estrogen, progesterone.",
                ),
            ],
        ),
    ],
}

# Maps catalog chapter keys to academic chapter.code
CHAPTER_CODE_BY_KEY: dict[str, str] = {
    "electrostatics": "electrostatics",
    "optics": "optics",
    "equilibrium": "equilibrium",
    "organic-basics": "organic-chemistry-basics",
    "cell": "cell-unit-of-life",
    "animal-kingdom": "animal-kingdom",
    "biomolecules": "biomolecules",
    "human-reproduction": "human-reproduction",
}
