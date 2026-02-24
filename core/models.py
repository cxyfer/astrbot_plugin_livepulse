from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Transition(enum.Enum):
    LIVE_START = "live_start"
    LIVE_END = "live_end"


@dataclass
class ChannelInfo:
    channel_id: str
    channel_name: str
    platform: str
    display_id: str = ""

    def __post_init__(self) -> None:
        if not self.display_id:
            self.display_id = self.channel_id

    def to_dict(self) -> dict:
        return {"channel_id": self.channel_id, "channel_name": self.channel_name, "platform": self.platform, "display_id": self.display_id}

    @classmethod
    def from_dict(cls, d: dict) -> ChannelInfo:
        return cls(channel_id=d["channel_id"], channel_name=d["channel_name"], platform=d["platform"], display_id=d.get("display_id", d["channel_id"]))


STATUS_EMOJI: dict[str, str] = {"live": "🟢", "offline": "🔴", "unknown": "❓"}


@dataclass
class StatusSnapshot:
    is_live: bool
    stream_id: str = ""
    title: str = ""
    category: str = ""
    thumbnail_url: str = ""
    streamer_name: str = ""
    stream_url: str = ""
    success: bool = True
    display_id: str | None = None


@dataclass
class MonitorEntry:
    channel_id: str
    channel_name: str
    last_status: str = "unknown"  # "live" | "offline" | "unknown"
    last_stream_id: str = ""
    initialized: bool = False
    display_id: str = ""

    def __post_init__(self) -> None:
        if not self.display_id:
            self.display_id = self.channel_id

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "last_status": self.last_status,
            "last_stream_id": self.last_stream_id,
            "initialized": self.initialized,
            "display_id": self.display_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MonitorEntry:
        return cls(
            channel_id=d["channel_id"],
            channel_name=d["channel_name"],
            last_status=d.get("last_status", "unknown"),
            last_stream_id=d.get("last_stream_id", ""),
            initialized=d.get("initialized", False),
            display_id=d.get("display_id", d["channel_id"]),
        )


@dataclass
class GroupState:
    language: str = "en"
    notify_enabled: bool = True
    end_notify_enabled: bool = True
    monitors: dict[str, dict[str, MonitorEntry]] = field(default_factory=dict)
    send_failure_count: int = 0

    def to_dict(self) -> dict:
        monitors_dict: dict[str, dict[str, dict]] = {}
        for platform, entries in self.monitors.items():
            monitors_dict[platform] = {cid: entry.to_dict() for cid, entry in entries.items()}
        return {
            "language": self.language,
            "notify_enabled": self.notify_enabled,
            "end_notify_enabled": self.end_notify_enabled,
            "monitors": monitors_dict,
            "send_failure_count": self.send_failure_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GroupState:
        monitors: dict[str, dict[str, MonitorEntry]] = {}
        for platform, entries in d.get("monitors", {}).items():
            monitors[platform] = {cid: MonitorEntry.from_dict(entry) for cid, entry in entries.items()}
        return cls(
            language=d.get("language", "en"),
            notify_enabled=d.get("notify_enabled", True),
            end_notify_enabled=d.get("end_notify_enabled", True),
            monitors=monitors,
            send_failure_count=d.get("send_failure_count", 0),
        )
