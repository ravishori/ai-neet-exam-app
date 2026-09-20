"""Local, deterministic NCERT-based subject classifier for unanswered PYQs.

No network calls. No LLM. See config.py::NETWORK_GUARD for the enforcement
mechanism and cli.py for the dry-run / --apply entrypoints.
"""

__version__ = "ncert-local-v1"
