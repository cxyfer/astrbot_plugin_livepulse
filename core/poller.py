from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiohttp import ClientSession

from astrbot.api import logger

from core.models import StatusSnapshot, Transition
from platforms.base import RateLimitError

if TYPE_CHECKING:
    from core.notifier import Notifier
    from core.store import Store
    from platforms.base import BasePlatformChecker

_BACKOFF_BASE = 30.0
_BACKOFF_MULT = 2.0
_BACKOFF_MAX = 300.0
_JITTER = 0.10


def _jittered(value: float) -> float:
    return value * (1 + random.uniform(-_JITTER, _JITTER))


@dataclass
class _PendingNotification:
    origin: str
    transition: Transition
    platform: str
    snapshot: StatusSnapshot
    streamer_name: str


class PlatformPoller:
    def __init__(
        self,
        checker: BasePlatformChecker,
        store: Store,
        notifier: Notifier,
        session: ClientSession,
        interval: int,
        global_notify: bool,
        global_end_notify: bool,
    ) -> None:
        self._checker = checker
        self._store = store
        self._notifier = notifier
        self._session = session
        self._interval = interval
        self._global_notify = global_notify
        self._global_end_notify = global_end_notify
        self._platform = checker.platform_name
        self._task: asyncio.Task | None = None
        self._channel_failures: dict[str, int] = {}
        self._channel_backoff_until: dict[str, float] = {}
        self._platform_backoff: float = 0.0
        self.healthy = True

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self._supervisor())
        return self._task

    def cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _supervisor(self) -> None:
        restart_count = 0
        while True:
            try:
                await self._poll_loop()
            except asyncio.CancelledError:
                return
            except Exception as e:
                self.healthy = False
                delay = min(_BACKOFF_BASE * (_BACKOFF_MULT ** restart_count), _BACKOFF_MAX)
                delay = _jittered(delay)
                logger.error(f"Poller {self._platform} crashed: {e}, restarting in {delay:.0f}s")
                restart_count += 1
                await asyncio.sleep(delay)
            else:
                break

    async def _poll_loop(self) -> None:
        while True:
            self.healthy = True
            snapshot = self._store.snapshot(self._platform)
            if not snapshot:
                await asyncio.sleep(self._interval)
                continue

            now = time.time()
            eligible = [cid for cid in snapshot if self._channel_backoff_until.get(cid, 0) <= now]

            if eligible:
                try:
                    statuses = await self._checker.check_status(eligible, self._session)
                    if self._platform_backoff > 0:
                        self._platform_backoff = max(self._platform_backoff / _BACKOFF_MULT, 0)
                        if self._platform_backoff < _BACKOFF_BASE:
                            self._platform_backoff = 0.0
                except RateLimitError:
                    self._apply_platform_backoff()
                    await asyncio.sleep(self._effective_interval())
                    continue
                except Exception as e:
                    logger.warning(f"Poller {self._platform} check failed: {e}")
                    await asyncio.sleep(self._effective_interval())
                    continue

                await self._process_results(statuses, snapshot)

            await asyncio.sleep(self._effective_interval())

    async def _process_results(
        self,
        statuses: dict[str, StatusSnapshot],
        snapshot: dict[str, set[str]],
    ) -> None:
        pending: list[_PendingNotification] = []

        async with self._store.lock:
            for channel_id, status in statuses.items():
                self._channel_failures.pop(channel_id, None)
                self._channel_backoff_until.pop(channel_id, None)

                origins = snapshot.get(channel_id, set())
                new_status = "live" if status.is_live else "offline"

                for origin in origins:
                    gs = self._store.get_group(origin)
                    if gs is None:
                        continue
                    entry = gs.monitors.get(self._platform, {}).get(channel_id)
                    if entry is None:
                        continue

                    transition = self._compute_transition(entry, new_status, status.stream_id)
                    self._store.update_status(origin, self._platform, channel_id, new_status, status.stream_id)

                    if transition is not None:
                        pending.append(_PendingNotification(
                            origin=origin,
                            transition=transition,
                            platform=self._platform,
                            snapshot=status,
                            streamer_name=status.streamer_name,
                        ))

            await self._store.persist()

        for note in pending:
            if note.transition == Transition.LIVE_START:
                await self._notifier.send_live_notification(
                    note.origin, note.platform, note.snapshot, self._global_notify,
                )
            elif note.transition == Transition.LIVE_END:
                await self._notifier.send_end_notification(
                    note.origin, note.platform, note.streamer_name,
                    self._global_notify, self._global_end_notify,
                )

    @staticmethod
    def _compute_transition(entry, new_status: str, new_stream_id: str) -> Transition | None:
        if not entry.initialized:
            return None
        if entry.last_status != "live" and new_status == "live":
            return Transition.LIVE_START
        if entry.last_status == "live" and new_status == "offline":
            return Transition.LIVE_END
        return None

    def _apply_platform_backoff(self) -> None:
        if self._platform_backoff == 0:
            self._platform_backoff = _BACKOFF_BASE
        else:
            self._platform_backoff = min(self._platform_backoff * _BACKOFF_MULT, _BACKOFF_MAX)
        logger.warning(f"Rate limited on {self._platform}, backoff {self._platform_backoff:.0f}s")

    def _effective_interval(self) -> float:
        return max(self._interval, _jittered(self._platform_backoff)) if self._platform_backoff else self._interval
