from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from astrbot.api import logger

CURRENT_SCHEMA_VERSION = 1
_MIGRATIONS: dict[int, callable] = {}


def _migrate(from_version: int):
    def decorator(fn):
        _MIGRATIONS[from_version] = fn
        return fn
    return decorator


class PersistenceManager:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "data.json"
        self.bak_path = data_dir / "data.json.bak"

    def load(self) -> dict:
        for p in (self.path, self.bak_path):
            if not p.exists():
                continue
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                return self._apply_migrations(raw)
            except Exception:
                logger.warning(f"Failed to load {p}, trying next fallback")
        logger.warning("No valid data file found, starting with empty state")
        return self._empty_state()

    def save(self, state: dict) -> None:
        state["schema_version"] = CURRENT_SCHEMA_VERSION
        payload = json.dumps(state, ensure_ascii=False, indent=2)
        if self.path.exists():
            shutil.copy2(str(self.path), str(self.bak_path))
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(str(tmp), str(self.path))

    def _apply_migrations(self, data: dict) -> dict:
        ver = data.get("schema_version", 1)
        if ver > CURRENT_SCHEMA_VERSION:
            logger.error(f"Unknown schema version {ver} (current: {CURRENT_SCHEMA_VERSION}), starting fresh")
            return self._empty_state()
        while ver < CURRENT_SCHEMA_VERSION:
            fn = _MIGRATIONS.get(ver)
            if fn is None:
                logger.error(f"No migration for version {ver}, starting fresh")
                return self._empty_state()
            data = fn(data)
            ver = data.get("schema_version", ver + 1)
        return data

    @staticmethod
    def _empty_state() -> dict:
        return {"schema_version": CURRENT_SCHEMA_VERSION, "groups": {}}
