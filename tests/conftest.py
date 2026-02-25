from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock astrbot before any plugin imports
_astrbot_mock = MagicMock()
_astrbot_mock.api.logger = MagicMock()
sys.modules.setdefault("astrbot", _astrbot_mock)
sys.modules.setdefault("astrbot.api", _astrbot_mock.api)
sys.modules.setdefault("astrbot.api.event", _astrbot_mock.api.event)
sys.modules.setdefault("astrbot.api.star", _astrbot_mock.api.star)

# Ensure plugin root is importable
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))
