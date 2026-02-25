from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import ChannelInfo, GroupState
from core.store import Store


def _make_store() -> Store:
    persistence = MagicMock()
    persistence.save = MagicMock()
    store = Store(persistence)
    return store


def _info(cid: str, name: str = "", platform: str = "twitch") -> ChannelInfo:
    return ChannelInfo(channel_id=cid, channel_name=name or cid, platform=platform)


class TestAddMonitorsBatch:
    @pytest.mark.asyncio
    async def test_single_lock_acquisition(self):
        store = _make_store()
        lock_count = {"acquired": 0}
        original_acquire = store.lock.acquire

        async def counting_acquire():
            lock_count["acquired"] += 1
            return await original_acquire()

        store.lock.acquire = counting_acquire

        items = [("twitch", _info("a")), ("twitch", _info("b"))]
        results = await store.add_monitors_batch("g1", items, 30, 500)

        assert lock_count["acquired"] == 1
        assert results == [None, None]

    @pytest.mark.asyncio
    async def test_single_persist_call(self):
        store = _make_store()
        items = [("twitch", _info("a")), ("twitch", _info("b")), ("twitch", _info("c"))]
        await store.add_monitors_batch("g1", items, 30, 500)

        assert store._persistence.save.call_count == 1

    @pytest.mark.asyncio
    async def test_incremental_limit(self):
        store = _make_store()
        items = [("twitch", _info(str(i))) for i in range(5)]
        results = await store.add_monitors_batch("g1", items, 3, 500)

        success = sum(1 for r in results if r is None)
        limited = sum(1 for r in results if r and "limit_group" in r)
        assert success == 3
        assert limited == 2

    @pytest.mark.asyncio
    async def test_reverse_index_consistency(self):
        store = _make_store()
        items = [("twitch", _info("a")), ("twitch", _info("b"))]
        await store.add_monitors_batch("g1", items, 30, 500)

        assert "a" in store.reverse_index.get("twitch", {})
        assert "b" in store.reverse_index.get("twitch", {})
        assert "g1" in store.reverse_index["twitch"]["a"]
        assert "g1" in store.reverse_index["twitch"]["b"]


class TestRemoveMonitorsBatch:
    @pytest.mark.asyncio
    async def test_single_lock_and_persist(self):
        store = _make_store()
        await store.add_monitors_batch("g1", [("twitch", _info("a")), ("twitch", _info("b"))], 30, 500)
        store._persistence.save.reset_mock()

        lock_count = {"acquired": 0}
        original_acquire = store.lock.acquire

        async def counting_acquire():
            lock_count["acquired"] += 1
            return await original_acquire()

        store.lock.acquire = counting_acquire

        results = await store.remove_monitors_batch("g1", [("twitch", "a"), ("twitch", "b")])

        assert lock_count["acquired"] == 1
        assert store._persistence.save.call_count == 1
        assert results == [True, True]

    @pytest.mark.asyncio
    async def test_reverse_index_after_remove(self):
        store = _make_store()
        await store.add_monitors_batch("g1", [("twitch", _info("a")), ("twitch", _info("b"))], 30, 500)
        await store.remove_monitors_batch("g1", [("twitch", "a")])

        assert "a" not in store.reverse_index.get("twitch", {})
        assert "b" in store.reverse_index.get("twitch", {})

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self):
        store = _make_store()
        results = await store.remove_monitors_batch("g1", [("twitch", "nope")])
        assert results == [False]
