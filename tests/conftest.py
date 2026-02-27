from __future__ import annotations

import sys
import tempfile as _tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

# --- Stub classes for astrbot framework ---


class _Star:
    """Minimal Star base class stub."""

    def __init__(self, context):
        self.context = context


class _Context:
    pass


def _register(*args, **kwargs):
    """Passthrough decorator that returns the class unchanged."""

    def decorator(cls):
        return cls

    return decorator


class _FilterNamespace:
    """Stub for filter.command_group / filter.command."""

    @staticmethod
    def command_group(name):
        def decorator(func):
            func._commands = {}

            def command(cmd_name):
                def cmd_decorator(method):
                    func._commands[cmd_name] = method
                    return method

                return cmd_decorator

            func.command = command
            return func

        return decorator


# --- Mock DiscordEmbed ---


class MockDiscordEmbed:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_mock_discord_components = MagicMock()
_mock_discord_components.DiscordEmbed = MockDiscordEmbed

sys.modules["astrbot.core.platform"] = MagicMock()
sys.modules["astrbot.core.platform.sources"] = MagicMock()
sys.modules["astrbot.core.platform.sources.discord"] = MagicMock()
sys.modules["astrbot.core.platform.sources.discord.components"] = (
    _mock_discord_components
)

# --- Build astrbot mock with real stubs ---

_api_star_mod = ModuleType("astrbot.api.star")
_api_star_mod.Star = _Star
_api_star_mod.Context = _Context
_api_star_mod.register = _register

_api_event_mod = MagicMock()
_api_event_mod.filter = _FilterNamespace()
_api_event_mod.AstrMessageEvent = MagicMock

_api_mod = ModuleType("astrbot.api")
_api_mod.logger = MagicMock()
_api_mod.AstrBotConfig = dict
_api_mod.event = _api_event_mod
_api_mod.star = _api_star_mod
_api_mod.message_components = MagicMock()

_astrbot_mod = ModuleType("astrbot")
_astrbot_mod.api = _api_mod

sys.modules["astrbot"] = _astrbot_mod
sys.modules["astrbot.api"] = _api_mod
sys.modules["astrbot.api.event"] = _api_event_mod
sys.modules["astrbot.api.star"] = _api_star_mod
sys.modules["astrbot.api.message_components"] = _api_mod.message_components

# --- Mock astrbot.core.utils ---

_mock_core = MagicMock()
_mock_core_utils = MagicMock()
_mock_astrbot_path = MagicMock()
_mock_astrbot_path.get_astrbot_data_path = lambda: _tempfile.mkdtemp()
sys.modules["astrbot.core"] = _mock_core
sys.modules["astrbot.core.utils"] = _mock_core_utils
sys.modules["astrbot.core.utils.astrbot_path"] = _mock_astrbot_path

# --- Ensure plugin root is importable ---

_PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))
