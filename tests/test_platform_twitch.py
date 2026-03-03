"""Tests TwitchChecker.check_status image_url resolution and snapshot construction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platforms.twitch import TwitchChecker


_TEMPLATE_URL = "https://static-cdn.jtvnw.net/previews-ttv/live_user_ninja-{width}x{height}.jpg"
_STREAM_DATA = {
    "data": [
        {
            "user_login": "ninja",
            "user_name": "Ninja",
            "id": "stream123",
            "title": "Fortnite Tournament",
            "game_name": "Fortnite",
            "thumbnail_url": _TEMPLATE_URL,
        }
    ]
}


def _make_checker() -> TwitchChecker:
    return TwitchChecker(client_id="cid", client_secret="csec", timeout=5)


class TestCheckStatusImageUrl:
    @pytest.mark.asyncio
    async def test_thumbnail_template_resolved_to_1280x720(self):
        """check_status replaces {width}/{height} template with 1280x720."""
        checker = _make_checker()
        session = MagicMock()

        with (
            patch.object(checker, "_ensure_token", new=AsyncMock(return_value="tok")),
            patch.object(
                checker, "_get_with_retry", new=AsyncMock(return_value=_STREAM_DATA)
            ),
        ):
            result = await checker.check_status(["ninja"], session)

        snapshot = result["ninja"]
        assert snapshot.is_live is True
        assert "1280x720" in snapshot.image_url
        assert "{width}" not in snapshot.image_url
        assert "{height}" not in snapshot.image_url

    @pytest.mark.asyncio
    async def test_snapshot_fields_populated_from_api(self):
        """check_status maps Helix stream fields to StatusSnapshot correctly."""
        checker = _make_checker()
        session = MagicMock()

        with (
            patch.object(checker, "_ensure_token", new=AsyncMock(return_value="tok")),
            patch.object(
                checker, "_get_with_retry", new=AsyncMock(return_value=_STREAM_DATA)
            ),
        ):
            result = await checker.check_status(["ninja"], session)

        snapshot = result["ninja"]
        assert snapshot.stream_id == "stream123"
        assert snapshot.title == "Fortnite Tournament"
        assert snapshot.category == "Fortnite"
        assert snapshot.streamer_name == "Ninja"
        assert snapshot.stream_url == "https://www.twitch.tv/ninja"

    @pytest.mark.asyncio
    async def test_offline_channel_returns_not_live(self):
        """Channel absent from API data is reported as not live."""
        checker = _make_checker()
        session = MagicMock()

        with (
            patch.object(checker, "_ensure_token", new=AsyncMock(return_value="tok")),
            patch.object(
                checker, "_get_with_retry", new=AsyncMock(return_value={"data": []})
            ),
        ):
            result = await checker.check_status(["offline_user"], session)

        assert result["offline_user"].is_live is False
