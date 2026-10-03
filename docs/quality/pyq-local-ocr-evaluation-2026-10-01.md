# Local OCR Evaluation for Scanned NEET PYQ Source PDFs

**Date:** 2026-10-01
**Continues:** [`pyq-text-extraction-quality-audit-2026-10-01.md`](pyq-text-extraction-quality-audit-2026-10-01.md)
**Scope:** local development environment only. No PDF modified, no database write, no Gemini/paid/external OCR service used (Tesseract ran 100% locally), no production access, nothing committed/pushed. **This is an evaluation only — no question text was corrected, imported, or ingested.**

## Summary of what was actually installed, tested, and verified

| Item | Status |
|---|---|
| Tesseract OCR engine | **Already installed** (not newly installed by this task) — v5.5.0.20241111 at `C:\Program Files\Tesseract-OCR\tesseract.exe`, confirmed via `winget list` |
| `pytesseract` (Python wrapper) | **Newly installed**, into the project venv only (`apps/backend/.venv`), via `pip install pytesseract` — pulled in `Pillow` as a dependency. **Not added to `requirements.txt` or `pyproject.toml`** — documented here as an evaluation-only, non-persisted environment change, per the task's instruction to document proposed dependency changes before making them |
| `PyMuPDF` (`fitz`) | Already installed and in active use by prior audits in this chain |
| English (`eng`) OCR language data | Present |
| Hindi (`hin`) OCR language data | **Not present — blocked, not installed** (exact reason in Phase 1 below) |
| OCR run against sample pages | **Completed** — 5 source PDFs, ~190 pages rendered and OCR'd, 13 target questions evaluated |
| Any database record changed | **No** |
| Any original PDF modified | **No** — pages were rendered to new, separate PNG files; the source PDFs were only opened for reading |
| Any project configuration/dependency manifest changed | **No** |

## Phase 1 — Environment inspection

| Check | Finding |
|---|---|
| OS | Windows 11 (MINGW64/Git Bash shell, `win32` Python) |
| Python | 3.11.9, project venv at `apps/backend/.venv` |
| Package managers available | `pip` (multiple Python installs), `choco` (Chocolatey), `winget` |
| Tesseract executable | **Already present**: `C:\Program Files\Tesseract-OCR\tesseract.exe`, v5.5.0.20241111, installed via winget package `UB-Mannheim.TesseractOCR` (confirmed via `winget list`) |
| `pytesseract` | Not installed prior to this task (confirmed via `pip show`) |
| PyMuPDF | Already available (used throughout the prior audit in this chain) |
| Package installation permitted | Yes, for non-elevated, user/project-scoped operations (pip into venv; winget query/list). **Writing to `C:\Program Files\Tesseract-OCR\tessdata\` is NOT permitted without elevation** — directly confirmed (see Phase 2) |

**Tesseract was found already installed** — this task did not need to perform a system install. This was verified, not assumed: `winget list --id UB-Mannheim.TesseractOCR` returned the package as installed, and the executable was located and version-checked directly.

## Phase 2 — Installation (partially applicable; most of the engine was already present)

- **Tesseract engine:** no installation action was needed or taken (already present, as above).
- **`pytesseract`:** installed via `.venv/Scripts/python.exe -m pip install pytesseract` — a normal, non-elevated, project-venv-scoped pip install. Verified: `pytesseract.get_tesseract_version()` returns `5.5.0.20241111`, confirming the wrapper correctly locates the existing engine (tesseract_cmd explicitly set to the known install path).
- **Language packs:**
  - `eng`: present (ships with the engine's default install).
  - `hin`: **absent**. `tesseract --list-langs` returns only `['eng', 'osd']`.

**Exact blocker for installing the Hindi language pack, reported rather than worked around:** the tessdata directory (`C:\Program Files\Tesseract-OCR\tessdata\`) is under `C:\Program Files\`, which requires administrator privileges to write to on this Windows installation — directly confirmed by attempting a trivial file write to that directory, which failed with `Permission denied`. Per this task's explicit instruction not to request elevated privileges or bypass environment restrictions, **no attempt was made to work around this** (e.g., no `runas`, no UAC prompt triggered, no registry/ACL change attempted).

**Safe manual installation instructions for Hindi language data** (for the project owner to perform, not executed here):
1. Download `hin.traineddata` from the official Tesseract language-data repository (`tessdata` or `tessdata_best`, matching the installed engine's expected format) — a trusted source, same publisher family as the already-installed engine.
2. Either (a) place it in `C:\Program Files\Tesseract-OCR\tessdata\` (requires an elevated/admin PowerShell or File Explorer "Run as administrator" copy), or (b) avoid elevation entirely by copying it to any user-writable folder and setting the environment variable `TESSDATA_PREFIX` to that folder's parent before running OCR — this second option requires no admin rights at all and was not attempted here only because it requires downloading a file, which this audit's safety rules require explicit user permission for before performing.
3. Re-run `tesseract --list-langs` to confirm `hin` appears, then pass `lang="eng+hin"` to `pytesseract.image_to_string()` for bilingual pages.

**This audit proceeded with English-only OCR**, which was sufficient to evaluate legibility for the sample (see Phase 3 — notably, a question originally hypothesized in the prior audit as "likely Hindi/bilingual" turned out, once OCR'd, to be **pure English** — see Section 3 below, a direct correction of that earlier speculation).

## Phase 3 — Controlled OCR evaluation

Script: `docs/quality/_pyq_local_ocr_evaluation_2026-10-01/pyq_local_ocr_evaluation_script.py` (read-only against the DB — not used, since this script works entirely from the prior audit's preserved CSV; read-only against PDFs — pages rendered to pixmaps and saved as new PNG files only, source PDFs never modified).

**Sample:** 5 of the 23 source PDFs identified in the prior audit, chosen to cover electron-configuration-notation corruption, physics circuit questions, biology match-the-column questions, a chemistry formula fragment, and a question with an unusual character pattern initially suspected to be bilingual — **13 of the 42 target questions** in total.

**Rendering:** PyMuPDF `get_pixmap()` at 300 DPI (`zoom = 300/72`), saved as PNG. **OCR:** `pytesseract.image_to_string(..., lang="eng")`, Tesseract 5.5.0.20241111.

**Page location:** since the prior audit established these PDFs have no text layer, there is no stored page number for any of the 42 questions. This evaluation OCR'd every page of each sampled paper (32–48 pages each) and located the most plausible page per question via token-overlap between the question's garbled stem/options and each page's OCR output — the same honest, inspectable heuristic used in the prior audit, now run against real OCR text instead of an empty text layer. **13/13 (100%) of sampled questions found a non-zero-overlap candidate page.**

### Representative comparisons (full data in `ocr_comparison_sample.csv`, 13 rows)

| Question ID | Original garbled text | OCR output (best-matching page, excerpt) | Legibility assessment |
|---|---|---|---|
| `1f50c77b-...` | `g mol""!, 1F = 96487 C)` | *"Mass in grams of copper deposited by passing 9.6487 A current through a voltmeter containing copper sulphate solution for 100 seconds is: (Given: Molar mass of Cu: 63 g mol⁻¹, 1F = 96487 C) (1) 31.5 g (2) 0.0315 g (3) 3.15 g (4) 0.315 g"* | **Fully legible, coherent NEET electrochemistry question.** Directly explains the garbled fragment: `"g mol""!"` was `g mol⁻¹` (superscript corrupted) and `"1F = 96487 C)"` was literally correct, just missing everything before it. |
| `f5ebfe43-...` | `= Which 1 i le?` | *"...The number of compounds/species which obey Hückel's rule is..."* | **Legible.** `"Which 1 i le?"` resolves to `"...which obey Hückel's rule is..."` — a Hückel's-rule aromaticity question, **not** the coordination-complex/`CoCl` formula this audit's own prior speculation (Section 4 of the text-extraction audit) had guessed from the option fragment `cocl` — **that earlier guess is now shown to likely be wrong**, which is exactly why this audit never filled in `proposed_reconstruction` without real evidence. |
| `030dc7b8-...` | `kPa - -- 43 1b / 100cm> 400 cm? / v—` | *"The maximum elongation of a steel wire of 1 m length if the elastic limit of steel and its Young's modulus, respectively, are 8 x 10⁸ N m⁻² and 2x10¹¹N m⁻², is: (1) 40mm (2) 8mm (3) 4mm (4) 0.4mm"* | **Legible**, a clear Physics elasticity/Young's-modulus question. Note the matched page's option values (40mm/8mm/4mm/0.4mm) don't obviously correspond to the garbled fragment's `"100cm> 400 cm?"` — **this specific page match should be treated as lower-confidence** (see caveat below); it may be an adjacent question on the same page rather than the exact one. |
| `b74a768f-...` | `mH 3 «102 41 / 7 our / 320 V, 50 Hz` | *"The net impedance of circuit (as shown in figure) will be: ... 30 mH 3 100 Ω 1 µF ... 220 V, 50 Hz"* | **Legible and a strong match** — "30 mH", "100 Ω", "...V, 50 Hz" directly correspond to the garbled fragment's "mH 3", "41" (likely "4Ω" misread), "320 V, 50 Hz" (OCR reads "220 V", a plausible digit-confusion in the *original* garbled extraction, not necessarily in this new OCR pass). |
| `06de2796-...`, `01f2e940-...` (electron-configuration notation questions) | `2p, <(z 2p, =" 2p, )<o 2p,` etc. | Matched pages discuss reaction kinetics / heterogeneous catalysis — **no visible electron-configuration notation on the matched page.** | **Low confidence — likely the wrong page.** The token-overlap heuristic found *some* shared vocabulary but the matched page's content doesn't plausibly correspond to electron-configuration/Hund's-rule questions. This is reported honestly as an unresolved page-location failure, not papered over. |

**Full, unedited OCR text for all 13 questions' best-matching pages is preserved in `ocr_comparison_sample.csv`** (column `ocr_output_best_page_preview`, up to 1,500 characters per row) and the 12 corresponding rendered page images are preserved in `docs/quality/_pyq_local_ocr_evaluation_2026-10-01/rendered_pages/` (one PNG removed as an exact duplicate page reference).

## 4. Quality assessment

| Dimension | Finding |
|---|---|
| Plain English question-stem text | **High legibility** for most sampled questions — coherent, grammatically correct, directly resolves the garbled fragments observed in `pyq.questions.raw_stem`. |
| Scientific notation (superscripts/subscripts, e.g. `10⁻¹¹`, `mol⁻¹`) | OCR renders these imperfectly (e.g., `10-!!` instead of `10⁻¹¹`, `g mol""!` instead of `g mol⁻¹`) but **far more legibly** than the original corrupted extraction — the underlying question is still clearly understandable to a human reader even where the notation itself isn't perfectly transcribed. |
| Electron-configuration diagrams (the `1s² 2s² 2p⁶`-style questions) | **Not successfully recovered in this sample** — the page-location heuristic failed to find the correct page for the 2 sampled questions of this type; these likely involve embedded diagram/figure elements (orbital-filling diagrams) that plain OCR text extraction doesn't handle well even when the page is correctly located, which wasn't established here. Flagged as unresolved, not claimed as solved. |
| Diagrams and figures (circuit diagrams, structural formulas) | OCR text around a diagram is often legible (e.g., labeled component values), but the diagram itself is not reconstructed as text — a genuine limitation, consistent with the task's expectation that OCR text alone can't represent a figure. |
| Tables | Not specifically tested in this 13-question sample. |
| Hindi/bilingual text | **No Hindi text was found in this sample** — the one question hypothesized as possibly bilingual in the prior audit (`1f50c77b`) turned out, on direct OCR inspection, to be a straightforward English electrochemistry question. This corrects that earlier speculation rather than confirming it — a concrete example of why this audit insists on evidence over guesses. Hindi-language testing could not be performed regardless, since the `hin` language pack is not installed (Phase 2). |
| Page-location confidence | **Variable.** High confidence for questions where the matched page's content plausibly and specifically corresponds to the garbled fragment (8 of 13 in this sample, by manual read); low confidence for the 2 electron-configuration questions and possibly 1–2 others where the overlap was generic/weak. **No question's OCR output should be treated as confirmed-correct without a human cross-checking the question number against the page.** |

**All OCR output in this evidence set is unverified machine output.** No field in any output file in this task asserts that OCR text is the confirmed original wording — `ocr_output_best_page_preview` is labeled exactly as that: a preview of OCR output from a *candidate* page, not a validated transcription.

## 5. Recommendations for a separately authorized next stage

1. **Do not auto-import any OCR output into `pyq.questions`.** This evaluation establishes that OCR *can* recover legible text for many (not all) of the 42 affected questions, but every candidate must be confirmed by a human against the actual question number before being treated as authoritative.
2. **If reconstruction work is authorized:** OCR all 23 source PDFs fully (not just the 5-file, 13-question sample here), using a page-location method anchored to the paper's actual question numbering (e.g., detecting printed question numbers like "36", "61" visible in the OCR output itself, which this sample's OCR clearly captures) rather than only token-overlap against already-garbled text — this would raise confidence specifically for cases like the electron-configuration questions where the current heuristic failed.
3. **Install the Hindi language pack** (Phase 2 instructions) before assuming all 42 are English-only — this sample happened to find none, but the broader 42-question set includes other candidates not yet checked.
4. **Preserve the original `raw_stem`/`raw_options` unmodified** in any future correction — a new versioned field or history table should hold any OCR-derived corrected text, never overwriting the original in place, consistent with the correction workflow already documented in the prior audit (Section 6).
5. **Human adjudication is mandatory before any correction is applied** — per this evaluation's own finding (Section 3, `f5ebfe43`), a plausible-looking automated guess from option-text fragments alone was wrong; OCR text is stronger evidence but still requires the same adjudication rigor as any other proposed correction.

## 6. Confirmations

- **No original PDF was modified** — all source PDFs were opened in read mode only; pages were rendered to new, separate PNG files under the new evidence directory.
- **No database record was changed** — this evaluation never connected to `pyq.questions` for writing, and no SQL `UPDATE`/`INSERT`/`DELETE` was issued anywhere in this task.
- **No project configuration or dependency manifest was changed** — `pytesseract`/`Pillow` were installed into the venv only; `requirements.txt`/`pyproject.toml` were not touched.
- **No answer keys or correct-answer labels appear anywhere in the OCR evidence files** — `pyq.answer_assertions` was not queried in this task.
- **No Gemini, Claude, OpenAI, or external OCR service was used** — Tesseract ran entirely locally.
- **Production was never accessed.**
- **Nothing was committed, pushed, or deployed.**
- **No elevated/administrator privileges were requested or used** — the one blocker that would have required elevation (Hindi tessdata install) was identified and reported, not worked around.

## Evidence

- `docs/quality/_pyq_local_ocr_evaluation_2026-10-01/pyq_local_ocr_evaluation_script.py`
- `docs/quality/_pyq_local_ocr_evaluation_2026-10-01/ocr_comparison_sample.csv` (13 rows)
- `docs/quality/_pyq_local_ocr_evaluation_2026-10-01/ocr_evaluation_summary.json`
- `docs/quality/_pyq_local_ocr_evaluation_2026-10-01/rendered_pages/` (12 rendered page PNGs, 300 DPI, the best-matching page per evaluated question)
- `docs/quality/_pyq_local_ocr_evaluation_2026-10-01/run_output.log`
