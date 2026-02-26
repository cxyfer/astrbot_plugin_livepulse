from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock


# Mock DiscordEmbed first (before any imports)
class MockDiscordEmbed:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# Create mock discord components module
_mock_discord_components = MagicMock()
_mock_discord_components.DiscordEmbed = MockDiscordEmbed
sys.modules["astrbot"] = MagicMock()
sys.modules["astrbot.core"] = MagicMock()
sys.modules["astrbot.core.platform"] = MagicMock()
sys.modules["astrbot.core.platform.sources"] = MagicMock()
sys.modules["astrbot.core.platform.sources.discord"] = MagicMock()
sys.modules["astrbot.core.platform.sources.discord.components"] = (
    _mock_discord_components
)

# Mock astrbot before any plugin imports
_astrbot_mock = MagicMock()
_astrbot_mock.api.logger = MagicMock()
_astrbot_mock.api.message_components = MagicMock()
_astrbot_mock.api.event.MessageChain = MagicMock()
sys.modules["astrbot"] = _astrbot_mock
sys.modules["astrbot.api"] = _astrbot_mock.api
sys.modules["astrbot.api.event"] = _astrbot_mock.api.event
sys.modules["astrbot.api.star"] = _astrbot_mock.api.star
sys.modules["astrbot.api.message_components"] = _astrbot_mock.api.message_components

# Ensure plugin root is importable
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))
