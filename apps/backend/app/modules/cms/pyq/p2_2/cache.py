"""P2.2 recovery cache."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RecoveryCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = cache_dir / "cache_index.json"
        self._index: dict[str, str] = {}
        if self.index_path.exists():
            self._index = json.loads(self.index_path.read_text(encoding="utf-8"))

    def _key(self, source_hash: str, request_hash: str, provider: str) -> str:
        return f"{source_hash}:{request_hash}:{provider}"

    def get(self, source_hash: str, request_hash: str, provider: str) -> dict[str, Any] | None:
        k = self._key(source_hash, request_hash, provider)
        path = self._index.get(k)
        if not path:
            return None
        p = self.cache_dir / path
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def put(self, source_hash: str, request_hash: str, provider: str, payload: dict[str, Any]) -> None:
        k = self._key(source_hash, request_hash, provider)
        fname = f"{k.replace(':', '_')}.json"
        (self.cache_dir / fname).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._index[k] = fname
        self.index_path.write_text(json.dumps(self._index, indent=2), encoding="utf-8")
