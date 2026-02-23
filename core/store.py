from __future__ import annotations

import asyncio

from astrbot.api import logger

from .models import GroupState, MonitorEntry, ChannelInfo
from .persistence import PersistenceManager


class Store:
    def __init__(self, persistence: PersistenceManager, default_language: str = "en") -> None:
        self.lock = asyncio.Lock()
        self.groups: dict[str, GroupState] = {}
        self.reverse_index: dict[str, dict[str, set[str]]] = {}  # {platform: {channel_id: {origins}}}
        self._persistence = persistence
        self._default_language = default_language

    # --- load / persist ---

    def load(self, data: dict) -> None:
        self.groups.clear()
        self.reverse_index.clear()
        for origin, gdata in data.get("groups", {}).items():
            gs = GroupState.from_dict(gdata)
            self.groups[origin] = gs
            for platform, entries in gs.monitors.items():
                for cid in entries:
                    self.reverse_index.setdefault(platform, {}).setdefault(cid, set()).add(origin)

    async def persist(self) -> None:
        state = {"groups": {origin: gs.to_dict() for origin, gs in self.groups.items()}}
        self._persistence.save(state)

    # --- helpers ---

    def _ensure_group(self, origin: str) -> GroupState:
        if origin not in self.groups:
            self.groups[origin] = GroupState(language=self._default_language)
        return self.groups[origin]

    def _count_global_channels(self) -> int:
        seen: set[tuple[str, str]] = set()
        for platform, channels in self.reverse_index.items():
            for cid in channels:
                seen.add((platform, cid))
        return len(seen)

    def _count_group_monitors(self, origin: str) -> int:
        gs = self.groups.get(origin)
        if gs is None:
            return 0
        return sum(len(entries) for entries in gs.monitors.values())

    # --- mutations (must be called under lock) ---

    def add_monitor(
        self, origin: str, platform: str, info: ChannelInfo,
        max_per_group: int, max_global: int,
    ) -> str | None:
        """Returns error key or None on success."""
        gs = self._ensure_group(origin)
        plat_monitors = gs.monitors.setdefault(platform, {})
        if info.channel_id in plat_monitors:
            return "cmd.add.duplicate"
        if self._count_group_monitors(origin) >= max_per_group:
            return "cmd.add.limit_group"
        is_new_channel = info.channel_id not in self.reverse_index.get(platform, {})
        if is_new_channel and self._count_global_channels() >= max_global:
            return "cmd.add.limit_global"
        plat_monitors[info.channel_id] = MonitorEntry(
            channel_id=info.channel_id,
            channel_name=info.channel_name,
        )
        self.reverse_index.setdefault(platform, {}).setdefault(info.channel_id, set()).add(origin)
        return None

    def remove_monitor(self, origin: str, platform: str, channel_id: str) -> bool:
        gs = self.groups.get(origin)
        if gs is None:
            return False
        plat_monitors = gs.monitors.get(platform)
        if plat_monitors is None or channel_id not in plat_monitors:
            return False
        del plat_monitors[channel_id]
        if not plat_monitors:
            del gs.monitors[platform]
        rev = self.reverse_index.get(platform, {}).get(channel_id)
        if rev:
            rev.discard(origin)
            if not rev:
                del self.reverse_index[platform][channel_id]
                if not self.reverse_index[platform]:
                    del self.reverse_index[platform]
        return True

    def set_language(self, origin: str, lang: str) -> None:
        self._ensure_group(origin).language = lang

    def set_notify(self, origin: str, enabled: bool) -> None:
        gs = self._ensure_group(origin)
        gs.notify_enabled = enabled
        if enabled:
            gs.send_failure_count = 0

    def set_end_notify(self, origin: str, enabled: bool) -> None:
        self._ensure_group(origin).end_notify_enabled = enabled

    def update_status(self, origin: str, platform: str, channel_id: str, status: str, stream_id: str) -> None:
        gs = self.groups.get(origin)
        if gs is None:
            return
        entry = gs.monitors.get(platform, {}).get(channel_id)
        if entry is None:
            return
        entry.last_status = status
        entry.last_stream_id = stream_id
        entry.initialized = True

    def increment_failure(self, origin: str) -> int:
        gs = self.groups.get(origin)
        if gs is None:
            return 0
        gs.send_failure_count += 1
        if gs.send_failure_count >= 10:
            gs.notify_enabled = False
            logger.warning(f"Auto-disabled notifications for {origin} after 10 consecutive failures")
        return gs.send_failure_count

    def reset_failure(self, origin: str) -> None:
        gs = self.groups.get(origin)
        if gs:
            gs.send_failure_count = 0

    # --- read (snapshot for pollers) ---

    def snapshot(self, platform: str) -> dict[str, set[str]]:
        """Returns {channel_id: frozenset(group_origins)} for the given platform."""
        rev = self.reverse_index.get(platform, {})
        return {cid: set(origins) for cid, origins in rev.items()}

    def get_language(self, origin: str) -> str:
        gs = self.groups.get(origin)
        return gs.language if gs else self._default_language

    def get_group(self, origin: str) -> GroupState | None:
        return self.groups.get(origin)
