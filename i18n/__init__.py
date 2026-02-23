from __future__ import annotations

import json
from pathlib import Path


_LOCALE_ALIASES: dict[str, str] = {"zh": "zh-Hans"}


class I18nManager:
    def __init__(self, i18n_dir: Path) -> None:
        self.strings: dict[str, dict[str, str]] = {}
        for f in i18n_dir.glob("*.json"):
            locale = f.stem
            with open(f, encoding="utf-8") as fh:
                self.strings[locale] = json.load(fh)

    def _resolve(self, locale: str) -> str:
        return _LOCALE_ALIASES.get(locale, locale)

    def get(self, locale: str, key: str, **kwargs: object) -> str:
        locale = self._resolve(locale)
        text = self.strings.get(locale, {}).get(key)
        if text is None:
            text = self.strings.get("en", {}).get(key, f"[{key}]")
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError, IndexError):
                return text
        return text
