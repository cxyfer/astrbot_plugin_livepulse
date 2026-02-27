"""Task 2.5: initialize() failure cleanup — no leaked tasks/session."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_plugin():
    from main import LivePulsePlugin

    plugin = object.__new__(LivePulsePlugin)
    plugin.config = {
        "youtube_timeout": 20,
        "bilibili_timeout": 10,
        "twitch_interval": 120,
        "youtube_interval": 300,
        "bilibili_interval": 180,
        "enable_notifications": True,
        "enable_end_notifications": True,
        "include_thumbnail": True,
        "default_language": "en",
    }
    plugin._checkers = {}
    plugin._pollers = []
    plugin._poller_tasks = []
    plugin._session = None
    plugin._notifier = None
    plugin._bg_tasks = set()
    plugin._initialized = False
    plugin._terminated = False

    plugin._persistence = MagicMock()
    plugin._persistence.load.return_value = {}
    plugin._i18n = MagicMock()

    plugin._store = MagicMock()
    plugin._store.load = MagicMock()

    plugin.context = MagicMock()
    plugin.name = "astrbot_plugin_livepulse"
    return plugin


@pytest.fixture
def plugin():
    return _make_plugin()


class TestInitFailureCleanup:
    @pytest.mark.asyncio
    async def test_init_failure_clears_state(self, plugin):
        """Mock Notifier construction to raise → verify no leaked resources."""
        with patch("main.Notifier", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                await plugin.initialize()

        assert plugin._initialized is False
        assert plugin._session is None
        assert plugin._notifier is None
        assert plugin._pollers == []
        assert plugin._poller_tasks == []
        assert plugin._checkers == {}

    @pytest.mark.asyncio
    async def test_reinitialize_after_failure(self, plugin):
        """After a failed init, a second call should succeed normally."""
        call_count = 0

        original_notifier = None

        def notifier_factory(*args, **kwargs):
            nonlocal call_count, original_notifier
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first-fail")
            from unittest.mock import MagicMock

            original_notifier = MagicMock()
            return original_notifier

        with patch("main.Notifier", side_effect=notifier_factory), patch(
            "main.PlatformPoller"
        ) as MockPoller:
            mock_task = AsyncMock()
            mock_task.done.return_value = False
            mock_task.cancel = MagicMock()
            MockPoller.return_value.start.return_value = asyncio.ensure_future(
                asyncio.sleep(999)
            )

            with pytest.raises(RuntimeError, match="first-fail"):
                await plugin.initialize()

            assert plugin._initialized is False

            await plugin.initialize()

            assert plugin._initialized is True
            assert plugin._notifier is original_notifier
            assert len(plugin._pollers) > 0

            # Cleanup tasks created during test
            for t in plugin._poller_tasks:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
