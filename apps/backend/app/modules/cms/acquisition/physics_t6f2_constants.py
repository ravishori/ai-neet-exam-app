"""T6-F2 controlled publication — Physics T6-F1 drafts only.

Never touches legacy-5000, T6-D historical 100, or T6-F1 rejected bank items.
"""

from __future__ import annotations

BATCH_ID = "physics-t6f1-pilot-20260902"
T6D_BATCH_ID = "physics-t6d-pilot-20260902"
LEGACY_BATCH = "legacy-physics-5000-import-20260902"
MODEL_USED = "t6f2-publish"  # ≤20 chars
PROMPT_VERSION = "t6f2-20260902-v1"  # ≤20 chars
EXPECTED_STAGED = 938
EXPECTED_REJECTED_CANDIDATES = 62
LEGACY_FINGERPRINT_EXPECTED = "937c60a9aaa5dcbedfa9b5bc569d45a0"
