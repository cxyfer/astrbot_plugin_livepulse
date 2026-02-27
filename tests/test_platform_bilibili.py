"""Tests Bilibili HTTP 429 → RateLimitError, non-429 → None, 200 → valid stream info."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.models import ChannelInfo
from platforms.base import RateLimitError
from platforms.bilibili import BilibiliChecker


def _mock_response(status: int, json_data: dict | None = None):
    resp = AsyncMock()
    resp.status = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestCheckStatus429:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self):
        checker = BilibiliChecker(timeout=5)
        session = MagicMock()
        session.post = MagicMock(return_value=_mock_response(429))

        with pytest.raises(RateLimitError):
            await checker.check_status(["12345"], session)

    @pytest.mark.asyncio
    async def test_non_429_error_returns_failed_snapshot(self):
        checker = BilibiliChecker(timeout=5)
        session = MagicMock()
        session.post = MagicMock(return_value=_mock_response(500))

        result = await checker.check_status(["12345"], session)
        assert "12345" in result
        assert result["12345"].success is False

    @pytest.mark.asyncio
    async def test_200_returns_valid_snapshot(self):
        checker = BilibiliChecker(timeout=5)
        json_data = {
            "data": {
                "12345": {
                    "live_status": 1,
                    "room_id": 999,
                    "title": "Test",
                    "area_v2_name": "Gaming",
                    "cover_from_user": "https://img.example.com/cover.jpg",
                    "uname": "TestUser",
                }
            }
        }
        session = MagicMock()
        session.post = MagicMock(return_value=_mock_response(200, json_data))

        result = await checker.check_status(["12345"], session)
        snap = result["12345"]
        assert snap.is_live is True
        assert snap.streamer_name == "TestUser"
        assert snap.title == "Test"


class TestResolveRoomId429:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self):
        checker = BilibiliChecker(timeout=5)
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(429))

        with pytest.raises(RateLimitError):
            await checker._resolve_room_id("100", session)

    @pytest.mark.asyncio
    async def test_non_429_error_returns_none(self):
        checker = BilibiliChecker(timeout=5)
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(500))

        result = await checker._resolve_room_id("100", session)
        assert result is None

    @pytest.mark.asyncio
    async def test_200_returns_uid(self):
        checker = BilibiliChecker(timeout=5)
        json_data = {"data": {"uid": 12345}}
        session = MagicMock()
        session.get = MagicMock(return_value=_mock_response(200, json_data))

        result = await checker._resolve_room_id("100", session)
        assert result == "12345"


class TestValidateUid429:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit(self):
        checker = BilibiliChecker(timeout=5)
        session = MagicMock()
        session.post = MagicMock(return_value=_mock_response(429))

        with pytest.raises(RateLimitError):
            await checker._validate_uid("12345", session)

    @pytest.mark.asyncio
    async def test_non_429_error_returns_none(self):
        checker = BilibiliChecker(timeout=5)
        session = MagicMock()
        session.post = MagicMock(return_value=_mock_response(500))

        result = await checker._validate_uid("12345", session)
        assert result is None

    @pytest.mark.asyncio
    async def test_200_returns_channel_info(self):
        checker = BilibiliChecker(timeout=5)
        json_data = {"data": {"12345": {"uname": "TestUser"}}}
        session = MagicMock()
        session.post = MagicMock(return_value=_mock_response(200, json_data))

        result = await checker._validate_uid("12345", session)
        assert isinstance(result, ChannelInfo)
        assert result.channel_name == "TestUser"
