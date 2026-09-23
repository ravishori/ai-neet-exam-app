"""Seed the NEET academic hierarchy.

Chapter lists are the real NTA NEET syllabus (a representative subset per
subject, not the full ~20 chapters each — see docs/decisions/ADR-0012 and
the CTO review's "seed one chapter completely before scaling" guidance).
One chapter per subject is fully fleshed out with topics + concepts to
prove the pipeline; the rest exist as chapters only, ready for Sprint 3's
ECAEP content authoring to fill in.
"""

from datetime import UTC

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.academic.models import Chapter, Concept, Exam, Subject, Topic

logger = get_logger("seed")

# (code, name, weightage_percent, class_level, topics)
# class_level ∈ {"11", "12", None}: NCERT class ownership from RS-003-B-1A.
# Biology XI Biomolecules is project-owned by BOTANY (class 11) — owner decision
# CF-C4b (canonical kebo109.pdf Ch 9). Not an NCERT Botany/Zoology claim.
# topics: list of (code, name, concepts) — only populated for the one
# "fully fleshed" chapter per subject; every other chapter has topics=[].
PHYSICS_CHAPTERS = [
    ("kinematics", "Kinematics", 3.0, "11", []),
    ("laws-of-motion", "Laws of Motion", 3.0, "11", []),
    ("work-energy-power", "Work, Energy and Power", 4.0, "11", []),
    ("gravitation", "Gravitation", 2.0, "11", []),
    ("thermodynamics-physics", "Thermodynamics", 4.0, "11", []),
    ("electrostatics", "Electrostatics", 5.0, "12", []),
    (
        "current-electricity",
        "Current Electricity",
        4.0,
        "12",
        [
            (
                "ohms-law",
                "Electric Current and Ohm's Law",
                [
                    ("ohms-law-concept", "Ohm's Law", "V = IR relationship between voltage, current, and resistance."),
                    ("drift-velocity", "Drift Velocity", "Average velocity of free electrons under an applied electric field."),
                ],
            ),
            (
                "resistance-resistivity",
                "Resistance and Resistivity",
                [
                    ("factors-affecting-resistance", "Factors Affecting Resistance", "Dependence of resistance on length, area, material, and temperature."),
                ],
            ),
            (
                "kirchhoffs-laws",
                "Kirchhoff's Laws",
                [
                    ("kcl-kvl", "Kirchhoff's Current and Voltage Laws", "Conservation of charge and energy applied to electrical circuits."),
                ],
            ),
        ],
    ),
    ("optics", "Optics", 5.0, "12", []),
    # T4 P0 chapter stubs (topic/concept trees applied via PhysicsP0TaxonomyService;
    # Gravitation fill remains deferred — chapter stub pre-existed above).
    ("units-and-measurement", "Units and Measurement", 2.0, "11", []),
    ("systems-of-particles-rotational-motion", "Systems of Particles and Rotational Motion", 4.0, "11", []),
    ("mechanical-properties-of-solids", "Mechanical Properties of Solids", 2.0, "11", []),
    ("mechanical-properties-of-fluids", "Mechanical Properties of Fluids", 2.0, "11", []),
    ("kinetic-theory", "Kinetic Theory", 2.0, "11", []),
]

CHEMISTRY_CHAPTERS = [
    ("basic-concepts-chemistry", "Some Basic Concepts of Chemistry", 3.0, "11", []),
    ("structure-of-atom", "Structure of Atom", 3.0, "11", []),
    (
        "chemical-bonding",
        "Chemical Bonding and Molecular Structure",
        5.0,
        "11",
        [
            (
                "ionic-bonding",
                "Ionic Bonding",
                [
                    ("lattice-energy", "Lattice Energy", "Energy released when gaseous ions combine to form an ionic solid."),
                ],
            ),
            (
                "covalent-bonding-vsepr",
                "Covalent Bonding and VSEPR Theory",
                [
                    ("vsepr-theory", "VSEPR Theory", "Predicting molecular geometry from electron pair repulsion."),
                ],
            ),
            (
                "hybridization",
                "Hybridization",
                [
                    ("sp-sp2-sp3", "sp, sp2, sp3 Hybridization", "Mixing of atomic orbitals to form new hybrid orbitals of equal energy."),
                ],
            ),
        ],
    ),
    ("thermodynamics-chemistry", "Thermodynamics", 4.0, "11", []),
    ("equilibrium", "Equilibrium", 4.0, "11", []),
    ("redox-reactions", "Redox Reactions", 2.0, "11", []),
    ("organic-chemistry-basics", "Organic Chemistry - Basic Principles", 4.0, "11", []),
    # ---- Chemistry Class 12 ----
    # RS-003-C1: nine NCERT Class 12 chapters (NCERT chs 1, 3-10) scaffolded
    # after the pre-existing electrochemistry entry. Topics and concepts are
    # derived from the verified NCERT Class 12 Chemistry PDFs on disk under
    # StudyMaterial/Chemistry/Class 12- Chemistry/ncert-books-class-12-
    # chemistry-chapter-N.pdf; see the CF-C1 implementation report for the
    # per-chapter section-heading provenance. neet_weightage_percent is left
    # None on the additions because no owner-verified NEET table for these
    # chapters is stored in the repo (see report §J).
    ("electrochemistry", "Electrochemistry", 3.0, "12", []),
    (
        "solutions",
        "Solutions",
        None,
        "12",
        [
            (
                "types-and-concentration-of-solutions",
                "Types and Concentration of Solutions",
                [
                    ("types-of-solutions", "Types of Solutions", "NCERT XII Ch 1 §1.1 — nine binary solutions (gas/liquid/solid solute × gas/liquid/solid solvent)."),
                    ("concentration-expressions", "Concentration Expressions", "NCERT XII Ch 1 §1.2 — mass %, volume %, ppm, mole fraction, molarity and molality."),
                ],
            ),
            (
                "raoults-law-and-vapour-pressure",
                "Raoult's Law and Vapour Pressure",
                [
                    ("raoults-law", "Raoult's Law", "NCERT XII Ch 1 — the partial vapour pressure of each volatile component is proportional to its mole fraction."),
                    ("ideal-and-non-ideal-solutions", "Ideal and Non-Ideal Solutions", "NCERT XII Ch 1 — deviations from Raoult's law and their molecular origin."),
                ],
            ),
            (
                "colligative-properties",
                "Colligative Properties",
                [
                    ("boiling-and-freezing-point", "Boiling-Point Elevation and Freezing-Point Depression", "NCERT XII Ch 1 — relative lowering of vapour pressure, ΔTb, ΔTf, osmotic pressure."),
                    ("abnormal-molar-mass-vant-hoff", "Abnormal Molar Mass and van't Hoff Factor", "NCERT XII Ch 1 — association / dissociation and the van't Hoff factor i."),
                ],
            ),
        ],
    ),
    (
        "chemical-kinetics",
        "Chemical Kinetics",
        None,
        "12",
        [
            (
                "rate-of-a-chemical-reaction",
                "Rate of a Chemical Reaction",
                [
                    ("average-and-instantaneous-rate", "Average and Instantaneous Rate", "NCERT XII Ch 3 — definition and units; instantaneous rate as the limit of average rate."),
                    ("factors-affecting-rate", "Factors Affecting Rate", "NCERT XII Ch 3 — concentration, temperature, catalyst, surface area."),
                ],
            ),
            (
                "rate-law-and-order-of-reaction",
                "Rate Law and Order of Reaction",
                [
                    ("rate-expression-and-rate-constant", "Rate Expression and Rate Constant", "NCERT XII Ch 3 — order, molecularity, differential rate law."),
                    ("integrated-rate-equations", "Integrated Rate Equations", "NCERT XII Ch 3 — zero- and first-order integrated forms and half-lives."),
                ],
            ),
            (
                "temperature-dependence-of-rate",
                "Temperature Dependence of Rate",
                [
                    ("arrhenius-equation", "Arrhenius Equation", "NCERT XII Ch 3 — k = A·exp(−Ea/RT); activation energy and pre-exponential factor."),
                    ("collision-theory", "Collision Theory of Reaction Rates", "NCERT XII Ch 3 — effective collisions, steric and energy factors."),
                ],
            ),
        ],
    ),
    (
        "d-and-f-block-elements",
        "The d- and f-Block Elements",
        None,
        "12",
        [
            (
                "position-and-electronic-configuration-dblock",
                "Position and Electronic Configuration",
                [
                    ("transition-elements-electron-config", "Electronic Configuration of Transition Elements", "NCERT XII Ch 4 §4.2 — (n−1)d^1–10 ns^1–2; anomalous configurations of Cr and Cu."),
                ],
            ),
            (
                "general-properties-transition-metals",
                "General Properties of Transition Metals",
                [
                    ("variable-oxidation-states", "Variable Oxidation States", "NCERT XII Ch 4 §4.3 — origin in comparable (n−1)d and ns energies; oxide/fluoride examples."),
                    ("colour-magnetism-and-catalysis", "Colour, Magnetism and Catalytic Activity", "NCERT XII Ch 4 — d–d transitions, spin-only magnetic moment, catalytic surfaces."),
                ],
            ),
            (
                "important-compounds-of-transition-metals",
                "Important Compounds of Transition Metals",
                [
                    ("permanganate-and-dichromate", "Potassium Permanganate and Potassium Dichromate", "NCERT XII Ch 4 — preparation, structures, and standard redox reactions."),
                ],
            ),
            (
                "lanthanoids-and-actinoids",
                "Lanthanoids and Actinoids",
                [
                    ("lanthanoid-contraction", "Lanthanoid Contraction", "NCERT XII Ch 4 — steady decrease in atomic and ionic radii across the 4f series and its consequences."),
                    ("actinoid-contraction-comparison", "Actinoid Contraction and Comparison with Lanthanoids", "NCERT XII Ch 4 — 5f contraction is larger per element (poorer shielding); oxidation-state diversity."),
                ],
            ),
        ],
    ),
    (
        "coordination-compounds",
        "Coordination Compounds",
        None,
        "12",
        [
            (
                "werners-theory-and-terminology",
                "Werner's Theory and Basic Terminology",
                [
                    ("primary-and-secondary-valency", "Primary and Secondary Valencies", "NCERT XII Ch 5 §5.1 — Werner's postulates; coordination number and coordination sphere."),
                    ("ligands-and-denticity", "Ligands and Denticity", "NCERT XII Ch 5 — monodentate, bidentate, polydentate, chelating and ambidentate ligands."),
                ],
            ),
            (
                "nomenclature-of-coordination-compounds",
                "Nomenclature of Coordination Compounds",
                [
                    ("iupac-naming-rules", "IUPAC Naming Rules for Complexes", "NCERT XII Ch 5 §5.3 — order of ligands, prefixes, oxidation-state Roman numerals."),
                ],
            ),
            (
                "isomerism-in-coordination-compounds",
                "Isomerism in Coordination Compounds",
                [
                    ("structural-isomerism-complexes", "Structural Isomerism (Ionisation, Linkage, Coordination, Solvate)", "NCERT XII Ch 5 §5.4 — types of structural isomerism in coordination complexes."),
                    ("stereoisomerism-complexes", "Stereoisomerism (Geometrical and Optical)", "NCERT XII Ch 5 §5.4 — cis-trans and Δ/Λ isomers in square-planar and octahedral complexes."),
                ],
            ),
            (
                "bonding-in-coordination-compounds",
                "Bonding in Coordination Compounds",
                [
                    ("valence-bond-theory-complexes", "Valence Bond Theory (VBT)", "NCERT XII Ch 5 §5.5 — inner-orbital vs outer-orbital complexes; hybridisation and geometry."),
                    ("crystal-field-theory", "Crystal Field Theory (CFT)", "NCERT XII Ch 5 §5.5 — Δo splitting, spectrochemical series, high-spin vs low-spin d configurations."),
                ],
            ),
        ],
    ),
    (
        "haloalkanes-and-haloarenes",
        "Haloalkanes and Haloarenes",
        None,
        "12",
        [
            (
                "classification-and-nomenclature-halides",
                "Classification and Nomenclature",
                [
                    ("primary-secondary-tertiary-halides", "Primary, Secondary and Tertiary Halides", "NCERT XII Ch 6 §6.1 — classification of C–X bearing carbon by degree of substitution."),
                    ("iupac-nomenclature-halides", "IUPAC Nomenclature of Haloalkanes and Haloarenes", "NCERT XII Ch 6 §6.2 — systematic naming rules for mono-, di- and poly-halogen compounds."),
                ],
            ),
            (
                "methods-of-preparation-haloalkanes",
                "Methods of Preparation of Haloalkanes",
                [
                    ("preparation-from-alcohols", "Preparation of Haloalkanes from Alcohols", "NCERT XII Ch 6 §6.4 — HX, PX3, PCl5, SOCl2 routes."),
                    ("preparation-from-hydrocarbons", "Preparation from Alkanes and Alkenes", "NCERT XII Ch 6 §6.4 — free-radical halogenation and Markovnikov addition."),
                ],
            ),
            (
                "substitution-and-elimination-reactions",
                "Substitution and Elimination Reactions",
                [
                    ("sn1-vs-sn2-mechanism", "SN1 vs SN2 Mechanism", "NCERT XII Ch 6 §6.7 — kinetics, stereochemistry and substrate-structure dependence."),
                    ("e1-vs-e2-elimination", "E1 vs E2 Elimination and Saytzeff Rule", "NCERT XII Ch 6 §6.7 — competition with substitution; Saytzeff/Hofmann orientation."),
                ],
            ),
            (
                "haloarenes-and-polyhalogen-compounds",
                "Haloarenes and Polyhalogen Compounds of Importance",
                [
                    ("nucleophilic-substitution-in-haloarenes", "Nucleophilic Substitution in Haloarenes", "NCERT XII Ch 6 — reduced reactivity due to resonance; conditions for aromatic SN."),
                    ("common-polyhalogen-uses", "Common Polyhalogen Compounds and Their Uses", "NCERT XII Ch 6 — chloroform, iodoform, DDT, freons and environmental concerns."),
                ],
            ),
        ],
    ),
    (
        "alcohols-phenols-and-ethers",
        "Alcohols, Phenols and Ethers",
        None,
        "12",
        [
            (
                "alcohols-classification-and-preparation",
                "Alcohols — Classification and Preparation",
                [
                    ("classification-of-alcohols", "Classification of Alcohols", "NCERT XII Ch 7 §7.1 — 1°, 2°, 3°; monohydric, dihydric, trihydric."),
                    ("preparation-of-alcohols", "Preparation of Alcohols from Alkenes and Carbonyl Compounds", "NCERT XII Ch 7 — hydration, hydroboration and Grignard routes."),
                ],
            ),
            (
                "physical-and-chemical-properties-of-alcohols",
                "Physical and Chemical Properties of Alcohols",
                [
                    ("hydrogen-bonding-and-boiling-point", "Hydrogen Bonding and Boiling Point Trends", "NCERT XII Ch 7 — origin of high boiling point relative to ethers/haloalkanes."),
                    ("acidity-esterification-oxidation-alcohols", "Acidity, Esterification and Oxidation of Alcohols", "NCERT XII Ch 7 — reactions with active metals, acyl chlorides and oxidising agents."),
                ],
            ),
            (
                "phenols-preparation-and-reactions",
                "Phenols — Preparation and Reactions",
                [
                    ("industrial-preparation-of-phenol", "Industrial Preparation of Phenol", "NCERT XII Ch 7 — cumene process; from diazonium salts."),
                    ("electrophilic-substitution-in-phenol", "Electrophilic Substitution in Phenol", "NCERT XII Ch 7 — activating, ortho/para directing effect; Kolbe and Reimer–Tiemann reactions."),
                ],
            ),
            (
                "ethers-preparation-and-reactions",
                "Ethers — Preparation and Reactions",
                [
                    ("williamson-ether-synthesis", "Williamson Ether Synthesis", "NCERT XII Ch 7 — alkoxide + alkyl halide; scope and limitations."),
                    ("cleavage-of-ethers-by-hi", "Cleavage of Ethers by HI/HBr", "NCERT XII Ch 7 — mechanism and product selectivity in aryl-alkyl ethers."),
                ],
            ),
        ],
    ),
    (
        "aldehydes-ketones-and-carboxylic-acids",
        "Aldehydes, Ketones and Carboxylic Acids",
        None,
        "12",
        [
            (
                "nomenclature-and-structure-carbonyl",
                "Nomenclature and Structure of the Carbonyl Group",
                [
                    ("iupac-nomenclature-carbonyl", "IUPAC Nomenclature of Aldehydes and Ketones", "NCERT XII Ch 8 §8.1 — systematic naming and common names."),
                    ("carbonyl-electronic-structure", "Electronic Structure of the Carbonyl Group", "NCERT XII Ch 8 §8.1 — sp² carbon, C=O polarity, resonance."),
                ],
            ),
            (
                "preparation-of-aldehydes-and-ketones",
                "Preparation of Aldehydes and Ketones",
                [
                    ("preparation-from-alcohols-hydrocarbons", "Preparation from Alcohols and Hydrocarbons", "NCERT XII Ch 8 §8.2 — oxidation of primary/secondary alcohols; ozonolysis; Rosenmund reduction."),
                ],
            ),
            (
                "reactions-of-aldehydes-and-ketones",
                "Reactions of Aldehydes and Ketones",
                [
                    ("nucleophilic-addition-carbonyl", "Nucleophilic Addition Reactions", "NCERT XII Ch 8 — HCN, NaHSO3, alcohols, ammonia derivatives."),
                    ("aldol-cannizzaro-reactions", "Aldol Condensation and Cannizzaro Reaction", "NCERT XII Ch 8 — α-H-based aldol; cross-Cannizzaro for α-H-free aldehydes."),
                ],
            ),
            (
                "carboxylic-acids-preparation-and-reactions",
                "Carboxylic Acids — Preparation and Reactions",
                [
                    ("preparation-of-carboxylic-acids", "Preparation of Carboxylic Acids", "NCERT XII Ch 8 §8.7 — from primary alcohols, aldehydes, nitriles and Grignard reagents."),
                    ("acidity-and-reactions-of-carboxylic-acids", "Acidity and Reactions of Carboxylic Acids", "NCERT XII Ch 8 — pKa trends; conversion to acid derivatives; Hell–Volhard–Zelinsky."),
                ],
            ),
        ],
    ),
    (
        "amines",
        "Amines",
        None,
        "12",
        [
            (
                "structure-and-classification-of-amines",
                "Structure and Classification of Amines",
                [
                    ("primary-secondary-tertiary-amines", "Primary, Secondary and Tertiary Amines", "NCERT XII Ch 9 §9.1–§9.2 — sp³ N geometry; classification by substitution."),
                    ("nomenclature-of-amines", "Nomenclature of Amines", "NCERT XII Ch 9 §9.3 — IUPAC and common naming for aliphatic and aromatic amines."),
                ],
            ),
            (
                "preparation-and-basicity-of-amines",
                "Preparation and Basicity of Amines",
                [
                    ("preparation-of-amines", "Preparation of Amines", "NCERT XII Ch 9 §9.4 — reduction of nitro/nitrile, Gabriel phthalimide, Hofmann bromamide."),
                    ("basicity-of-amines", "Basicity of Amines in Gas Phase and Aqueous Media", "NCERT XII Ch 9 §9.5 — inductive/steric/solvation effects on Kb ordering."),
                ],
            ),
            (
                "chemical-reactions-of-amines",
                "Chemical Reactions of Amines",
                [
                    ("acylation-and-alkylation-amines", "Acylation, Alkylation and Carbylamine Reactions", "NCERT XII Ch 9 §9.6 — key qualitative tests and derivative formation."),
                    ("hinsberg-test", "Hinsberg's Test for 1°/2°/3° Amines", "NCERT XII Ch 9 §9.6 — benzenesulfonyl chloride behaviour differentiates amine classes."),
                ],
            ),
            (
                "diazonium-salts",
                "Diazonium Salts",
                [
                    ("preparation-of-diazonium-salts", "Preparation of Aromatic Diazonium Salts", "NCERT XII Ch 9 §9.10 — diazotisation of aromatic primary amines with HNO2 at 0–5 °C."),
                    ("sandmeyer-and-coupling-reactions", "Sandmeyer and Coupling Reactions", "NCERT XII Ch 9 §9.10 — replacement of −N2+ by halogens/CN; azo dye formation."),
                ],
            ),
        ],
    ),
    (
        "biomolecules-chem",
        "Biomolecules",
        None,
        "12",
        [
            (
                "carbohydrates",
                "Carbohydrates",
                [
                    ("classification-of-carbohydrates", "Classification of Carbohydrates", "NCERT XII Ch 10 §10.1 — monosaccharides, oligosaccharides, polysaccharides; reducing vs non-reducing."),
                    ("structure-of-glucose-and-fructose", "Structure of Glucose and Fructose", "NCERT XII Ch 10 §10.1.2 — open-chain and Haworth forms; α/β anomers."),
                ],
            ),
            (
                "amino-acids-and-proteins",
                "Amino Acids and Proteins",
                [
                    ("classification-and-zwitterion", "Classification of Amino Acids and the Zwitterion", "NCERT XII Ch 10 — essential vs non-essential; isoelectric point."),
                    ("protein-structure-levels", "Primary, Secondary, Tertiary and Quaternary Structure of Proteins", "NCERT XII Ch 10 — peptide bonds, α-helix, β-sheet, folding and denaturation."),
                ],
            ),
            (
                "nucleic-acids",
                "Nucleic Acids",
                [
                    ("dna-vs-rna", "Structure and Function of DNA and RNA", "NCERT XII Ch 10 §10.5 — nucleotide monomers, base pairing, double helix; mRNA/tRNA/rRNA roles."),
                ],
            ),
            (
                "vitamins-and-hormones",
                "Vitamins and Hormones",
                [
                    ("vitamin-classification", "Classification of Vitamins", "NCERT XII Ch 10 §10.4 — fat-soluble (A, D, E, K) vs water-soluble (B, C); deficiency diseases."),
                ],
            ),
        ],
    ),
]

BOTANY_CHAPTERS = [
    ("the-living-world", "The Living World", 2.0, "11", []),
    ("plant-kingdom", "Plant Kingdom", 3.0, "11", []),
    ("morphology-flowering-plants", "Morphology of Flowering Plants", 3.0, "11", []),
    ("cell-unit-of-life", "Cell - The Unit of Life", 4.0, "11", []),
    (
        "photosynthesis",
        "Photosynthesis in Higher Plants",
        4.0,
        "11",
        [
            (
                "light-reaction",
                "Light Reaction",
                [
                    ("photophosphorylation", "Photophosphorylation", "ATP synthesis driven by the light-dependent electron transport chain."),
                ],
            ),
            (
                "dark-reaction",
                "Dark Reaction (Calvin Cycle)",
                [
                    ("c3-c4-pathway", "C3 vs C4 Pathway", "Two biochemical routes for carbon fixation with different efficiency under heat/light stress."),
                ],
            ),
            (
                "factors-affecting-photosynthesis",
                "Factors Affecting Photosynthesis",
                [
                    ("photorespiration", "Photorespiration", "Wasteful oxygenation pathway competing with carbon fixation in C3 plants."),
                    (
                        "limiting-factors",
                        "Limiting Factors (Blackman's Law)",
                        "The rate of photosynthesis is controlled by the factor nearest its minimal value (Blackman's Law of Limiting Factors, 1905), including external factors (light, CO2, temperature, water) and internal factors (leaf traits, chlorophyll amount, internal CO2).",
                    ),
                ],
            ),
        ],
    ),
    ("plant-growth-development", "Plant Growth and Development", 3.0, "11", []),
    # Project ownership BOTANY / class 11 — CF-C4b owner decision; source kebo109.pdf Ch 9.
    ("biomolecules", "Biomolecules", 3.0, "11", []),
    ("sexual-reproduction-flowering-plants", "Sexual Reproduction in Flowering Plants", 3.0, "12", []),
]

ZOOLOGY_CHAPTERS = [
    ("animal-kingdom", "Animal Kingdom", 4.0, "11", []),
    ("structural-organisation-animals", "Structural Organisation in Animals", 2.0, "11", []),
    ("digestion-absorption", "Digestion and Absorption", 2.0, "11", []),
    ("breathing-exchange-of-gases", "Breathing and Exchange of Gases", 3.0, "11", []),
    (
        "body-fluids-circulation",
        "Body Fluids and Circulation",
        4.0,
        "11",
        [
            (
                "blood-and-blood-groups",
                "Blood and Blood Groups",
                [
                    ("abo-blood-grouping", "ABO Blood Grouping System", "Classification of blood based on antigens present on red blood cells."),
                ],
            ),
            (
                "cardiac-cycle",
                "Cardiac Cycle",
                [
                    ("cardiac-cycle-phases", "Cardiac Cycle Phases", "Systole and diastole phases governing one heartbeat."),
                ],
            ),
            (
                "human-heart-anatomy",
                "Human Heart Anatomy",
                [
                    ("heart-structure", "Structure of the Human Heart", "Four chambers, valves, and major vessels of the heart."),
                ],
            ),
        ],
    ),
    ("human-reproduction", "Human Reproduction", 3.0, "12", []),
]

SUBJECTS = [
    ("PHYSICS", "Physics", PHYSICS_CHAPTERS),
    ("CHEMISTRY", "Chemistry", CHEMISTRY_CHAPTERS),
    ("BOTANY", "Botany", BOTANY_CHAPTERS),
    ("ZOOLOGY", "Zoology", ZOOLOGY_CHAPTERS),
]


async def seed_academic(session: AsyncSession) -> None:
    result = await session.execute(select(Exam).where(Exam.code == "NEET"))
    exam = result.scalar_one_or_none()
    if not exam:
        exam = Exam(code="NEET", name="NEET UG", description="National Eligibility cum Entrance Test (Undergraduate)")
        session.add(exam)
        await session.flush()
        logger.info("exam_seeded", code="NEET")

    # CF-C4b: Biology XI Biomolecules project ownership is BOTANY / class 11.
    # Reassign any leftover ZOOLOGY/biomolecules row (preserve chapter id + FKs)
    # before the subject loop can create a duplicate under BOTANY.
    botany_subj = (
        await session.execute(select(Subject).where(Subject.code == "BOTANY", Subject.deleted_at.is_(None)))
    ).scalar_one_or_none()
    zoology_subj = (
        await session.execute(select(Subject).where(Subject.code == "ZOOLOGY", Subject.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if botany_subj and zoology_subj:
        zoo_bio = (
            await session.execute(
                select(Chapter).where(
                    Chapter.subject_id == zoology_subj.id,
                    Chapter.code == "biomolecules",
                    Chapter.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        bot_bio = (
            await session.execute(
                select(Chapter).where(
                    Chapter.subject_id == botany_subj.id,
                    Chapter.code == "biomolecules",
                    Chapter.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if zoo_bio and not bot_bio:
            zoo_bio.subject_id = botany_subj.id
            zoo_bio.class_level = "11"
            await session.flush()
            logger.info("biomolecules_ownership_reconciled", from_subject="ZOOLOGY", to_subject="BOTANY")
        elif zoo_bio and bot_bio and zoo_bio.id != bot_bio.id:
            # Prefer the row that already has content; soft-delete the empty stub.
            from datetime import datetime

            zoo_q = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM cms.content_items ci
                        JOIN academic.concepts c ON c.id = ci.concept_id
                        JOIN academic.topics t ON t.id = c.topic_id
                        WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL
                        """
                    ),
                    {"cid": zoo_bio.id},
                )
            ).scalar_one()
            bot_q = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM cms.content_items ci
                        JOIN academic.concepts c ON c.id = ci.concept_id
                        JOIN academic.topics t ON t.id = c.topic_id
                        WHERE t.chapter_id = :cid AND ci.deleted_at IS NULL
                        """
                    ),
                    {"cid": bot_bio.id},
                )
            ).scalar_one()
            now = datetime.now(UTC)
            if zoo_q == 0 and bot_q >= 0:
                zoo_bio.deleted_at = now
                bot_bio.class_level = "11"
                logger.info("biomolecules_zoology_empty_stub_soft_deleted", chapter_id=str(zoo_bio.id))
            elif bot_q == 0 and zoo_q > 0:
                bot_bio.deleted_at = now
                zoo_bio.subject_id = botany_subj.id
                zoo_bio.class_level = "11"
                logger.info("biomolecules_botany_empty_stub_soft_deleted_moved_zoology")
            else:
                # Both have content — do not auto-delete; leave for operator.
                logger.warning(
                    "biomolecules_duplicate_chapters_manual_review",
                    zoology_id=str(zoo_bio.id),
                    botany_id=str(bot_bio.id),
                    zoo_q=zoo_q,
                    bot_q=bot_q,
                )
            await session.flush()

    for subject_order, (subject_code, subject_name, chapters) in enumerate(SUBJECTS):
        result = await session.execute(
            select(Subject).where(Subject.exam_id == exam.id, Subject.code == subject_code)
        )
        subject = result.scalar_one_or_none()
        if not subject:
            subject = Subject(exam_id=exam.id, code=subject_code, name=subject_name, display_order=subject_order)
            session.add(subject)
            await session.flush()
            logger.info("subject_seeded", code=subject_code)

        for chapter_order, (chapter_code, chapter_name, weightage, class_level, topics) in enumerate(chapters):
            result = await session.execute(
                select(Chapter).where(
                    Chapter.subject_id == subject.id,
                    Chapter.code == chapter_code,
                    Chapter.deleted_at.is_(None),
                )
            )
            chapter = result.scalar_one_or_none()
            if not chapter:
                chapter = Chapter(
                    subject_id=subject.id,
                    code=chapter_code,
                    name=chapter_name,
                    display_order=chapter_order,
                    neet_weightage_percent=weightage,
                    class_level=class_level,
                )
                session.add(chapter)
                await session.flush()
                logger.info("chapter_seeded", code=chapter_code)
            elif chapter.class_level != class_level:
                # Reconcile pre-existing chapter rows with the authoritative
                # class assignment (RS-003-B-1A). The migration performs the
                # same UPDATE; both must agree — see RS-003-B-1 §17.
                chapter.class_level = class_level

            for topic_order, (topic_code, topic_name, concepts) in enumerate(topics):
                result = await session.execute(
                    select(Topic).where(Topic.chapter_id == chapter.id, Topic.code == topic_code)
                )
                topic = result.scalar_one_or_none()
                if not topic:
                    topic = Topic(chapter_id=chapter.id, code=topic_code, name=topic_name, display_order=topic_order)
                    session.add(topic)
                    await session.flush()
                    logger.info("topic_seeded", code=topic_code)

                for concept_order, (concept_code, concept_name, summary) in enumerate(concepts):
                    result = await session.execute(
                        select(Concept).where(Concept.topic_id == topic.id, Concept.code == concept_code)
                    )
                    concept = result.scalar_one_or_none()
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
                        logger.info("concept_seeded", code=concept_code)

    await session.commit()
    logger.info("academic_seed_complete")
