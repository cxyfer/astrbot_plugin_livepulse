from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.batch import (
    BatchItem, detect_mode, preprocess,
    process_batch_add, process_batch_remove, MAX_BATCH_SIZE,
)
from core.models import ChannelInfo
from core.store import Store


_VALID_PLATFORMS = ("youtube", "twitch", "bilibili")


def _detect_platform(raw: str) -> str | None:
    from urllib.parse import urlparse
    _HOST_MAP = {
        "youtube.com": "youtube", "www.youtube.com": "youtube",
        "twitch.tv": "twitch", "www.twitch.tv": "twitch",
        "live.bilibili.com": "bilibili",
    }
    url = raw if "://" in raw else f"https://{raw}"
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    return _HOST_MAP.get(host.lower()) if host else None


def _make_store() -> Store:
    persistence = MagicMock()
    persistence.save = MagicMock()
    return Store(persistence)


def _info(cid: str, platform: str = "twitch") -> ChannelInfo:
    return ChannelInfo(channel_id=cid, channel_name=cid, platform=platform)


def _make_checker(platform: str, known: set[str]):
    checker = MagicMock()
    checker.platform_name = platform

    async def validate(identifier, session):
        extracted = checker.extract_id_from_url(identifier)
        cid = extracted or identifier
        if cid in known:
            return _info(cid, platform)
        return None

    checker.validate_channel = AsyncMock(side_effect=validate)
    checker.extract_id_from_url.return_value = ""
    return checker


class TestIntegrationCmdAdd:
    @pytest.mark.asyncio
    async def test_batch_add_platform_id(self):
        store = _make_store()
        checker = _make_checker("twitch", {"a", "b", "c"})
        checkers = {"twitch": checker}

        raw_args = ["twitch", "a", "b", "c"]
        _, items = detect_mode(raw_args, _VALID_PLATFORMS, _detect_platform)
        items, trunc = preprocess(items)

        result = await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        assert len(result.items) == 3
        assert all(r.status == "success" for r in result.items)
        gs = store.get_group("g1")
        assert len(gs.monitors["twitch"]) == 3

    @pytest.mark.asyncio
    async def test_batch_add_url(self):
        store = _make_store()
        checker = _make_checker("twitch", {"wpnebula", "streamer2"})
        checker.extract_id_from_url.side_effect = lambda url: (
            "wpnebula" if "wpnebula" in url else "streamer2" if "streamer2" in url else ""
        )
        checkers = {"twitch": checker}

        raw_args = ["https://www.twitch.tv/wpnebula", "https://www.twitch.tv/streamer2"]
        _, items = detect_mode(raw_args, _VALID_PLATFORMS, _detect_platform)
        items, trunc = preprocess(items)

        result = await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        assert len(result.items) == 2
        assert all(r.status == "success" for r in result.items)

    @pytest.mark.asyncio
    async def test_n1_unified_format(self):
        store = _make_store()
        checker = _make_checker("twitch", {"solo"})
        checkers = {"twitch": checker}

        raw_args = ["twitch", "solo"]
        _, items = detect_mode(raw_args, _VALID_PLATFORMS, _detect_platform)
        items, trunc = preprocess(items)

        result = await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        assert len(result.items) == 1
        assert result.items[0].status == "success"

    def test_mixed_mode_rejection(self):
        with pytest.raises(ValueError, match="mixed_mode"):
            detect_mode(
                ["twitch", "a", "https://www.twitch.tv/b"],
                _VALID_PLATFORMS, _detect_platform,
            )

    @pytest.mark.asyncio
    async def test_truncation_notice(self):
        store = _make_store()
        known = {str(i) for i in range(25)}
        checker = _make_checker("twitch", known)
        checkers = {"twitch": checker}

        raw_args = ["twitch"] + [str(i) for i in range(25)]
        _, items = detect_mode(raw_args, _VALID_PLATFORMS, _detect_platform)
        items, trunc = preprocess(items)

        assert trunc == 5
        assert len(items) == MAX_BATCH_SIZE


class TestIntegrationCmdRemove:
    @pytest.mark.asyncio
    async def test_batch_remove(self):
        store = _make_store()
        checker = _make_checker("twitch", {"a", "b"})
        checkers = {"twitch": checker}

        add_items = [BatchItem("twitch", "a"), BatchItem("twitch", "b")]
        await process_batch_add(store, "g1", add_items, checkers, None, 30, 500)

        rm_items = [BatchItem("twitch", "a"), BatchItem("twitch", "b")]
        result = await process_batch_remove(store, "g1", rm_items, checkers, None)

        assert all(r.status == "removed" for r in result.items)
