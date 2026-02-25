from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.batch import (
    BatchItem, process_batch_add, process_batch_remove, _SEM_LIMIT,
)
from core.models import ChannelInfo
from platforms.base import RateLimitError


# --- fixtures ---

def _make_store(monitors=None):
    store = MagicMock()
    store.lock = asyncio.Lock()
    store.add_monitors_batch = AsyncMock(return_value=[])
    store.remove_monitors_batch = AsyncMock(return_value=[])
    store.get_group.return_value = None
    store.lookup_by_display_id.return_value = None
    if monitors:
        gs = MagicMock()
        gs.monitors = monitors
        store.get_group.return_value = gs
    return store


def _make_checker(results: dict | None = None, raise_for: dict | None = None):
    checker = MagicMock()
    raise_for = raise_for or {}

    async def validate(identifier, session):
        if identifier in raise_for:
            raise raise_for[identifier]
        if results and identifier in results:
            return results[identifier]
        return None

    checker.validate_channel = AsyncMock(side_effect=validate)
    checker.extract_id_from_url.return_value = ""
    return checker


def _info(cid: str, name: str = "", platform: str = "twitch") -> ChannelInfo:
    return ChannelInfo(channel_id=cid, channel_name=name or cid, platform=platform)


# ===== 6.3 process_batch_add tests =====

class TestProcessBatchAdd:
    @pytest.mark.asyncio
    async def test_all_success(self):
        checkers = {"twitch": _make_checker({"a": _info("a"), "b": _info("b")})}
        store = _make_store()
        store.add_monitors_batch.return_value = [None, None]

        items = [BatchItem("twitch", "a"), BatchItem("twitch", "b")]
        result = await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        assert len(result.items) == 2
        assert all(r.status == "success" for r in result.items)
        store.add_monitors_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        checkers = {"twitch": _make_checker(
            results={"a": _info("a")},
            raise_for={"b": RateLimitError("twitch"), "c": RuntimeError("boom")},
        )}
        store = _make_store()
        store.add_monitors_batch.return_value = [None]

        items = [BatchItem("twitch", "a"), BatchItem("twitch", "b"),
                 BatchItem("twitch", "c"), BatchItem("twitch", "d")]
        result = await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        statuses = {r.identifier: r.status for r in result.items}
        assert statuses["a"] == "success"
        assert statuses["b"] == "rate_limited"
        assert statuses["c"] == "internal_error"
        assert statuses["d"] == "not_found"

    @pytest.mark.asyncio
    async def test_limit_group_mid_batch(self):
        checkers = {"twitch": _make_checker({"a": _info("a"), "b": _info("b"), "c": _info("c")})}
        store = _make_store()
        store.add_monitors_batch.return_value = [None, None, "cmd.add.limit_group"]

        items = [BatchItem("twitch", "a"), BatchItem("twitch", "b"), BatchItem("twitch", "c")]
        result = await process_batch_add(store, "g1", items, checkers, None, 2, 500)

        statuses = {r.identifier: r.status for r in result.items}
        assert statuses["a"] == "success"
        assert statuses["b"] == "success"
        assert statuses["c"] == "limit_group"

    @pytest.mark.asyncio
    async def test_duplicate_in_store(self):
        checkers = {"twitch": _make_checker({"a": _info("a")})}
        store = _make_store()
        store.add_monitors_batch.return_value = ["cmd.add.duplicate"]

        items = [BatchItem("twitch", "a")]
        result = await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        assert result.items[0].status == "duplicate"

    @pytest.mark.asyncio
    async def test_semaphore_concurrency_bound(self):
        peak = {"value": 0, "max": 0}
        real_sem = asyncio.Semaphore(_SEM_LIMIT)

        async def slow_validate(identifier, session):
            async with real_sem:
                peak["value"] += 1
                peak["max"] = max(peak["max"], peak["value"])
                await asyncio.sleep(0.01)
                peak["value"] -= 1
                return _info(identifier)

        checker = MagicMock()
        checker.validate_channel = AsyncMock(side_effect=slow_validate)
        checkers = {"twitch": checker}
        store = _make_store()
        store.add_monitors_batch.return_value = [None] * 10

        items = [BatchItem("twitch", str(i)) for i in range(10)]
        await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        assert peak["max"] <= _SEM_LIMIT


# ===== 6.4 process_batch_remove tests =====

class TestProcessBatchRemove:
    @pytest.mark.asyncio
    async def test_all_found(self):
        store = _make_store(monitors={"twitch": {"a": MagicMock(), "b": MagicMock()}})
        store.remove_monitors_batch.return_value = [True, True]

        items = [BatchItem("twitch", "a"), BatchItem("twitch", "b")]
        result = await process_batch_remove(store, "g1", items, {}, None)

        assert all(r.status == "removed" for r in result.items)

    @pytest.mark.asyncio
    async def test_partial_not_found(self):
        store = _make_store(monitors={"twitch": {"a": MagicMock()}})
        store.remove_monitors_batch.return_value = [True, False]

        items = [BatchItem("twitch", "a"), BatchItem("twitch", "missing")]
        result = await process_batch_remove(store, "g1", items, {}, None)

        assert result.items[0].status == "removed"
        assert result.items[1].status == "not_found"

    @pytest.mark.asyncio
    async def test_url_mode_with_network_resolution(self):
        checker = _make_checker(results={"https://live.bilibili.com/123": _info("uid456", platform="bilibili")})
        checker.extract_id_from_url.return_value = ""
        store = _make_store(monitors={"bilibili": {"uid456": MagicMock()}})
        store.remove_monitors_batch.return_value = [True]

        items = [BatchItem("bilibili", "https://live.bilibili.com/123")]
        result = await process_batch_remove(store, "g1", items, {"bilibili": checker}, None)

        assert result.items[0].status == "removed"

    @pytest.mark.asyncio
    async def test_display_id_fallback(self):
        store = _make_store(monitors={"twitch": {"real_id": MagicMock()}})
        store.lookup_by_display_id.return_value = "real_id"
        store.remove_monitors_batch.return_value = [True]

        items = [BatchItem("twitch", "display_name")]
        result = await process_batch_remove(store, "g1", items, {}, None)

        assert result.items[0].status == "removed"
        store.lookup_by_display_id.assert_called_with("g1", "twitch", "display_name")

    @pytest.mark.asyncio
    async def test_url_network_error_classified(self):
        checker = _make_checker(raise_for={"https://live.bilibili.com/bad": RateLimitError("bilibili")})
        checker.extract_id_from_url.return_value = ""
        store = _make_store()

        items = [BatchItem("bilibili", "https://live.bilibili.com/bad")]
        result = await process_batch_remove(store, "g1", items, {"bilibili": checker}, None)

        assert result.items[0].status == "rate_limited"
