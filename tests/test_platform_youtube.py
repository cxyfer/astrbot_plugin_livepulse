"""Tests YouTubeChecker._check_single HTML parsing and image_url construction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from platforms.youtube import YouTubeChecker


_VIDEO_ID = "dQw4w9WgXcQ"

# Minimal HTML that satisfies _check_single's live-stream detection logic.
_LIVE_HTML = (
    '<meta property="og:title" content="TestChannel">'
    '"canonicalBaseUrl":"/(@TestChannel)"'
    '"videoRenderer",'
    f'"videoId":"{_VIDEO_ID}",'
    '"title":{"runs":[{"text":"Test Stream"}]},'
    '"style":"LIVE"'
)

_OFFLINE_HTML = (
    '<meta property="og:title" content="TestChannel">'
    '"canonicalBaseUrl":"/(@TestChannel)"'
)


def _mock_session(html: str, status: int = 200) -> MagicMock:
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=html)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get = MagicMock(return_value=ctx)
    return session


class TestCheckSingleImageUrl:
    @pytest.mark.asyncio
    async def test_live_stream_image_url_uses_hqdefault(self):
        """_check_single constructs hqdefault.jpg URL from extracted video_id."""
        checker = YouTubeChecker(timeout=5)
        session = _mock_session(_LIVE_HTML)

        snapshot = await checker._check_single("UCxxxxxx", session)

        assert snapshot.is_live is True
        assert snapshot.image_url == f"https://img.youtube.com/vi/{_VIDEO_ID}/hqdefault.jpg"

    @pytest.mark.asyncio
    async def test_live_stream_image_url_contains_video_id(self):
        """image_url embeds the extracted video_id, not a hardcoded value."""
        checker = YouTubeChecker(timeout=5)
        session = _mock_session(_LIVE_HTML)

        snapshot = await checker._check_single("UCxxxxxx", session)

        assert _VIDEO_ID in snapshot.image_url

    @pytest.mark.asyncio
    async def test_offline_channel_returns_not_live(self):
        """Channel with no LIVE marker returns is_live=False."""
        checker = YouTubeChecker(timeout=5)
        session = _mock_session(_OFFLINE_HTML)

        snapshot = await checker._check_single("UCxxxxxx", session)

        assert snapshot.is_live is False
        assert snapshot.image_url == ""
