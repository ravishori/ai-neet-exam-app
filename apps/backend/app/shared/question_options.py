"""Normalizes a QUESTION content item's stored ``body["options"]`` into the
shape every API consumer (admin review packet, student assessment, public
search, factory review) expects: a list of ``{"label": str, "text": str}``.

Some PYQ ingestion paths wrote ``options`` as a dict keyed by letter
(``{"A": "...", "B": "..."}``) instead of the array shape the create-API's
validation enforces. A dict has no ``.map``/``.length``, so passing it
through unnormalized crashes both the admin content-detail page and every
student-facing question renderer with an uncaught TypeError (see F-17).

Format audit (F-17 follow-up, production DB, 19,589 QUESTION rows):
every ``options`` value observed in production is either a dict with
exactly keys A/B/C/D and string values (12,396 rows), or a list whose
every element is a dict with string ``label``/``text`` keys (7,193 rows).
No null, empty, duplicate-key (impossible for a JSON object), or
non-string-value case exists today. The branches below are still written
defensively for shapes that don't currently exist, since a future
ingestion path could reintroduce one:
- dict: sorted by key so A < B < C < D order survives regardless of
  insertion order; preserves every label/value, invents nothing, keeps
  an incomplete dict (e.g. only A/B) as a 2-item list rather than padding
  it to 4.
- list: passed through unchanged for items already shaped
  ``{"label": ..., "text": ...}`` (the only shape seen in production);
  any list element that is not a dict is dropped rather than rendered,
  since a bare string/number has no label and would otherwise reach
  React as an un-keyed, label-less row — dropping avoids that without
  inventing a label for content that was never associated with one.
- anything else (``None``, a string, a number, a bool) returns ``[]``,
  matching the pre-existing F-12 null-options behavior.
"""


def normalize_options(raw: object) -> list[dict]:
    if isinstance(raw, dict):
        return [{"label": label, "text": text} for label, text in sorted(raw.items())]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []
