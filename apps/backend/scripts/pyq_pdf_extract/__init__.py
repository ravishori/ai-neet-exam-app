"""Local, deterministic PDF-text extraction for two NEET study-material PDFs.

No AI/LLM calls. No database writes. No external uploads. All segmentation
is regex/heuristic based on PyMuPDF text (with a local Tesseract OCR
fallback for any page whose native text layer is too sparse to parse),
reusing the conventions already established in
`scripts/pyq_image_pipeline/extractor.py` and `ocr_extractor.py`.
"""
