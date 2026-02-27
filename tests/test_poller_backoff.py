"""Tests channel-level backoff logic in PlatformPoller._process_results."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.models import StatusSnapshot
from core.poller import _BACKOFF_BASE, _BACKOFF_MAX, PlatformPoller


def _make_poller() -> PlatformPoller:
    checker = MagicMock()
    checker.platform_name = "test"
    store = MagicMock()
    store.lock = asyncio.Lock()
    store.persist = AsyncMock()
    store.get_group.return_value = None
    notifier = MagicMock()
    session = MagicMock()
    return PlatformPoller(
        checker=checker,
        store=store,
        notifier=notifier,
        session=session,
        interval=60,
        global_notify=True,
        global_end_notify=True,
    )


class TestChannelBackoff:
    @pytest.mark.asyncio
    async def test_single_failure_sets_backoff(self):
        poller = _make_poller()
        statuses = {"ch1": StatusSnapshot(is_live=False, success=False)}
        snapshot = {"ch1": set()}
        before = time.time()
        await poller._process_results(statuses, snapshot)

        assert poller._channel_failures["ch1"] == 1
        until = poller._channel_backoff_until["ch1"]
        assert until >= before + _BACKOFF_BASE * 0.9

    @pytest.mark.asyncio
    async def test_backoff_non_decreasing_and_capped(self):
        poller = _make_poller()
        snapshot = {"ch1": set()}
        prev_delay = 0.0

        for i in range(1, 8):
            statuses = {"ch1": StatusSnapshot(is_live=False, success=False)}
            before = time.time()
            await poller._process_results(statuses, snapshot)
            until = poller._channel_backoff_until["ch1"]
            delay = until - before
            assert delay >= prev_delay * 0.8  # allow jitter tolerance
            assert delay <= _BACKOFF_MAX + 1.0
            prev_delay = delay

    @pytest.mark.asyncio
    async def test_success_clears_backoff(self):
        poller = _make_poller()
        snapshot = {"ch1": {"origin1"}}
        poller._store.get_group.return_value = None

        fail = {"ch1": StatusSnapshot(is_live=False, success=False)}
        await poller._process_results(fail, snapshot)
        assert "ch1" in poller._channel_failures

        ok = {"ch1": StatusSnapshot(is_live=False, success=True, streamer_name="x")}
        await poller._process_results(ok, snapshot)
        assert "ch1" not in poller._channel_failures
        assert "ch1" not in poller._channel_backoff_until

    @pytest.mark.asyncio
    async def test_cross_channel_independence(self):
        poller = _make_poller()
        snapshot = {"ch1": set(), "ch2": set()}
        statuses = {
            "ch1": StatusSnapshot(is_live=False, success=False),
            "ch2": StatusSnapshot(is_live=False, success=True, streamer_name="x"),
        }
        await poller._process_results(statuses, snapshot)

        assert "ch1" in poller._channel_failures
        assert "ch2" not in poller._channel_failures
        assert "ch1" in poller._channel_backoff_until
        assert "ch2" not in poller._channel_backoff_until
