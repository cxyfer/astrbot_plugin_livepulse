"""Task 5.6: YouTube concurrent polling with Semaphore."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import StatusSnapshot
from platforms.base import RateLimitError
from platforms.youtube import YouTubeChecker


class TestCheckStatusConcurrency:
    @pytest.mark.asyncio
    async def test_results_match_serial(self):
        """Concurrent execution produces same results as serial."""
        checker = YouTubeChecker(timeout=5)
        ids = [f"UC{i:022d}" for i in range(5)]
        expected = {
            cid: StatusSnapshot(is_live=False, streamer_name=cid) for cid in ids
        }

        async def fake_single(cid, session):
            return StatusSnapshot(is_live=False, streamer_name=cid)

        with patch.object(checker, "_check_single", side_effect=fake_single):
            session = MagicMock()
            result = await checker.check_status(ids, session)

        for cid in ids:
            assert result[cid].streamer_name == expected[cid].streamer_name
            assert result[cid].is_live == expected[cid].is_live

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """At most 10 channels checked concurrently."""
        checker = YouTubeChecker(timeout=5)
        ids = [f"UC{i:022d}" for i in range(20)]
        peak = 0
        current = 0
        lock = asyncio.Lock()

        async def counting_single(cid, session):
            nonlocal peak, current
            async with lock:
                current += 1
                if current > peak:
                    peak = current
            await asyncio.sleep(0.01)
            async with lock:
                current -= 1
            return StatusSnapshot(is_live=False, streamer_name=cid)

        with patch.object(checker, "_check_single", side_effect=counting_single):
            session = MagicMock()
            await checker.check_status(ids, session)

        assert peak <= 10

    @pytest.mark.asyncio
    async def test_rate_limit_propagates(self):
        """RateLimitError in one channel propagates from check_status."""
        checker = YouTubeChecker(timeout=5)

        async def failing_single(cid, session):
            if cid == "UC_BAD":
                raise RateLimitError("youtube")
            return StatusSnapshot(is_live=False, streamer_name=cid)

        with patch.object(checker, "_check_single", side_effect=failing_single):
            session = MagicMock()
            with pytest.raises(RateLimitError):
                await checker.check_status(["UC_OK", "UC_BAD"], session)

    @pytest.mark.asyncio
    async def test_non_rate_limit_error_yields_failed_snapshot(self):
        """Non-RateLimitError → failed snapshot in result, no propagation."""
        checker = YouTubeChecker(timeout=5)

        async def partial_fail(cid, session):
            if cid == "UC_FAIL":
                raise ValueError("network error")
            return StatusSnapshot(is_live=True, streamer_name=cid)

        with patch.object(checker, "_check_single", side_effect=partial_fail):
            session = MagicMock()
            result = await checker.check_status(["UC_OK", "UC_FAIL"], session)

        assert result["UC_OK"].is_live is True
        assert result["UC_FAIL"].success is False
        assert result["UC_FAIL"].is_live is False
