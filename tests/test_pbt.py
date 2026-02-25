from __future__ import annotations

import asyncio
import random
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.batch import BatchItem, process_batch_add, process_batch_remove
from core.models import ChannelInfo
from core.store import Store


def _make_store() -> Store:
    persistence = MagicMock()
    persistence.save = MagicMock()
    return Store(persistence)


def _info(cid: str, platform: str = "twitch") -> ChannelInfo:
    return ChannelInfo(channel_id=cid, channel_name=cid, platform=platform)


def _make_checker(platform: str, known: set[str]):
    checker = MagicMock()

    async def validate(identifier, session):
        if identifier in known:
            return _info(identifier, platform)
        return None

    checker.validate_channel = AsyncMock(side_effect=validate)
    checker.extract_id_from_url.return_value = ""
    return checker


class TestPBT:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("seed", range(5))
    async def test_idempotency(self, seed):
        """batch_add twice with same input -> same state"""
        rng = random.Random(seed)
        n = rng.randint(1, 10)
        ids = [f"ch{i}" for i in range(n)]

        store = _make_store()
        checker = _make_checker("twitch", set(ids))
        checkers = {"twitch": checker}
        items = [BatchItem("twitch", cid) for cid in ids]

        await process_batch_add(store, "g1", items, checkers, None, 30, 500)
        state1 = dict(store.get_group("g1").monitors.get("twitch", {}))

        await process_batch_add(store, "g1", items, checkers, None, 30, 500)
        state2 = dict(store.get_group("g1").monitors.get("twitch", {}))

        assert set(state1.keys()) == set(state2.keys())

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seed", range(5))
    async def test_commutativity(self, seed):
        """shuffled input -> same final state (given unique <= 20)"""
        rng = random.Random(seed)
        n = rng.randint(2, 15)
        ids = [f"ch{i}" for i in range(n)]

        checker = _make_checker("twitch", set(ids))
        checkers = {"twitch": checker}

        store1 = _make_store()
        items1 = [BatchItem("twitch", cid) for cid in ids]
        await process_batch_add(store1, "g1", items1, checkers, None, 30, 500)

        store2 = _make_store()
        shuffled = ids[:]
        rng.shuffle(shuffled)
        items2 = [BatchItem("twitch", cid) for cid in shuffled]
        await process_batch_add(store2, "g1", items2, checkers, None, 30, 500)

        keys1 = set(store1.get_group("g1").monitors.get("twitch", {}).keys())
        keys2 = set(store2.get_group("g1").monitors.get("twitch", {}).keys())
        assert keys1 == keys2

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seed", range(5))
    async def test_round_trip(self, seed):
        """add then remove -> original empty state"""
        rng = random.Random(seed)
        n = rng.randint(1, 10)
        ids = [f"ch{i}" for i in range(n)]

        store = _make_store()
        checker = _make_checker("twitch", set(ids))
        checkers = {"twitch": checker}

        items = [BatchItem("twitch", cid) for cid in ids]
        await process_batch_add(store, "g1", items, checkers, None, 30, 500)

        rm_items = [BatchItem("twitch", cid) for cid in ids]
        await process_batch_remove(store, "g1", rm_items, checkers, None)

        gs = store.get_group("g1")
        remaining = gs.monitors.get("twitch", {})
        assert len(remaining) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seed", range(5))
    async def test_invariant_monitor_count_le_limit(self, seed):
        """monitor count never exceeds limit"""
        rng = random.Random(seed)
        n = rng.randint(5, 20)
        limit = rng.randint(1, n - 1)
        ids = [f"ch{i}" for i in range(n)]

        store = _make_store()
        checker = _make_checker("twitch", set(ids))
        checkers = {"twitch": checker}

        items = [BatchItem("twitch", cid) for cid in ids]
        await process_batch_add(store, "g1", items, checkers, None, limit, 500)

        gs = store.get_group("g1")
        count = sum(len(e) for e in gs.monitors.values())
        assert count <= limit

    def test_mode_exclusivity_mixed_input(self):
        """mixed input -> ValueError, zero mutations possible"""
        from core.batch import detect_mode
        from urllib.parse import urlparse

        _HOST_MAP = {
            "twitch.tv": "twitch", "www.twitch.tv": "twitch",
            "youtube.com": "youtube", "www.youtube.com": "youtube",
        }

        def _detect(raw):
            url = raw if "://" in raw else f"https://{raw}"
            try:
                host = urlparse(url).hostname
            except ValueError:
                return None
            return _HOST_MAP.get(host.lower()) if host else None

        with pytest.raises(ValueError):
            detect_mode(
                ["twitch", "a", "https://www.twitch.tv/b"],
                ("youtube", "twitch", "bilibili"),
                _detect,
            )
