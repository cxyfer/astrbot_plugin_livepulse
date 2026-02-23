from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

# Ensure plugin root is on sys.path for relative imports
_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from core.notifier import Notifier
from core.persistence import PersistenceManager
from core.poller import PlatformPoller
from core.store import Store
from i18n import I18nManager
from platforms.base import RateLimitError
from platforms.bilibili import BilibiliChecker
from platforms.twitch import TwitchChecker
from platforms.youtube import YouTubeChecker

_VALID_PLATFORMS = ("youtube", "twitch", "bilibili")
_DATA_DIR = Path(os.path.expanduser("~")) / ".astrbot" / "livepulse"


@register("astrbot_plugin_livepulse", "Xyfer", "Multi-platform live stream monitor", "1.0.0")
class LivePulsePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config

        self._persistence = PersistenceManager(_DATA_DIR)
        self._i18n = I18nManager(_PLUGIN_DIR / "i18n")
        self._store = Store(self._persistence, default_language=config.get("default_language", "en"))

        self._checkers: dict[str, YouTubeChecker | TwitchChecker | BilibiliChecker] = {}
        self._pollers: list[PlatformPoller] = []
        self._poller_tasks: list[asyncio.Task] = []
        self._session: aiohttp.ClientSession | None = None
        self._initialized = False
        self._terminated = False

    # --- lifecycle ---

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        data = self._persistence.load()
        self._store.load(data)

        self._session = aiohttp.ClientSession(headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        })

        self._checkers["youtube"] = YouTubeChecker(timeout=self.config.get("youtube_timeout", 20))
        self._checkers["bilibili"] = BilibiliChecker(timeout=self.config.get("bilibili_timeout", 10))

        client_id = self.config.get("twitch_client_id", "")
        client_secret = self.config.get("twitch_client_secret", "")
        if client_id and client_secret:
            self._checkers["twitch"] = TwitchChecker(client_id, client_secret, timeout=self.config.get("twitch_timeout", 10))

        notifier = Notifier(
            self.context, self._store, self._i18n,
            include_thumbnail=self.config.get("include_thumbnail", True),
        )

        global_notify = self.config.get("enable_notifications", True)
        global_end_notify = self.config.get("enable_end_notifications", True)

        platform_intervals = {
            "youtube": self.config.get("youtube_interval", 300),
            "twitch": self.config.get("twitch_interval", 120),
            "bilibili": self.config.get("bilibili_interval", 180),
        }

        for name, checker in self._checkers.items():
            poller = PlatformPoller(
                checker=checker,
                store=self._store,
                notifier=notifier,
                session=self._session,
                interval=platform_intervals[name],
                global_notify=global_notify,
                global_end_notify=global_end_notify,
            )
            self._pollers.append(poller)
            self._poller_tasks.append(poller.start())

        logger.info(f"LivePulse initialized: {len(self._pollers)} pollers started")

    async def terminate(self) -> None:
        if self._terminated:
            return
        self._terminated = True

        for poller in self._pollers:
            poller.cancel()
        for task in self._poller_tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        if self._session and not self._session.closed:
            await self._session.close()

        async with self._store.lock:
            await self._store.persist()

        logger.info("LivePulse terminated")

    # --- helpers ---

    def _lang(self, event: AstrMessageEvent) -> str:
        return self._store.get_language(event.unified_msg_origin)

    def _t(self, event: AstrMessageEvent, key: str, **kwargs: object) -> str:
        return self._i18n.get(self._lang(event), key, **kwargs)

    def _get_checker(self, platform: str) -> YouTubeChecker | TwitchChecker | BilibiliChecker | None:
        return self._checkers.get(platform)

    # --- commands ---

    @filter.command_group("live")
    def live(self):
        pass

    @live.command("add")
    async def cmd_add(self, event: AstrMessageEvent, platform: str, channel_id: str):
        origin = event.unified_msg_origin
        platform = platform.lower()
        if platform not in _VALID_PLATFORMS:
            yield event.plain_result(self._t(event, "cmd.add.invalid_platform", platform=platform))
            return

        checker = self._get_checker(platform)
        if checker is None:
            yield event.plain_result(self._t(event, "cmd.add.twitch_no_creds"))
            return

        try:
            info = await checker.validate_channel(channel_id, self._session)
        except RateLimitError as e:
            yield event.plain_result(self._t(event, "error.rate_limited", platform=e.platform))
            return
        except Exception as e:
            logger.warning(f"validate_channel failed for {platform}/{channel_id}: {e}")
            yield event.plain_result(self._t(event, "cmd.add.invalid_channel", channel_id=channel_id))
            return
        if info is None:
            if platform == "bilibili" and not channel_id.isdigit() and "live.bilibili.com" not in channel_id:
                yield event.plain_result(self._t(event, "cmd.add.bilibili_hint"))
            else:
                yield event.plain_result(self._t(event, "cmd.add.invalid_channel", channel_id=channel_id))
            return

        max_per_group = self.config.get("max_monitors_per_group", 30)
        max_global = self.config.get("max_global_channels", 500)

        async with self._store.lock:
            err = self._store.add_monitor(origin, platform, info, max_per_group, max_global)
            if err:
                if "limit_group" in err:
                    yield event.plain_result(self._t(event, err, limit=max_per_group))
                elif "limit_global" in err:
                    yield event.plain_result(self._t(event, err, limit=max_global))
                elif "duplicate" in err:
                    yield event.plain_result(self._t(event, err, name=info.channel_name, channel_id=info.channel_id))
                return
            await self._store.persist()

        yield event.plain_result(self._t(event, "cmd.add.success", platform=platform, name=info.channel_name, channel_id=info.channel_id))

    @live.command("remove")
    async def cmd_remove(self, event: AstrMessageEvent, platform: str, channel_id: str):
        origin = event.unified_msg_origin
        platform = platform.lower()

        async with self._store.lock:
            removed = self._store.remove_monitor(origin, platform, channel_id)
            if removed:
                await self._store.persist()

        if removed:
            yield event.plain_result(self._t(event, "cmd.remove.success", platform=platform, channel_id=channel_id))
        else:
            yield event.plain_result(self._t(event, "cmd.remove.not_found", platform=platform, channel_id=channel_id))

    @live.command("list")
    async def cmd_list(self, event: AstrMessageEvent):
        origin = event.unified_msg_origin
        gs = self._store.get_group(origin)
        if gs is None or not any(gs.monitors.values()):
            yield event.plain_result(self._t(event, "cmd.list.empty"))
            return

        lines = [self._t(event, "cmd.list.header")]
        for platform, entries in gs.monitors.items():
            for cid, entry in entries.items():
                status = entry.last_status if entry.initialized else "unknown"
                lines.append(self._t(event, "cmd.list.entry", status=status, platform=platform, name=entry.channel_name, channel_id=cid))
        yield event.plain_result("\n".join(lines))

    @live.command("check")
    async def cmd_check(self, event: AstrMessageEvent, platform: str, channel_id: str):
        platform = platform.lower()
        if platform not in _VALID_PLATFORMS:
            yield event.plain_result(self._t(event, "cmd.add.invalid_platform", platform=platform))
            return

        checker = self._get_checker(platform)
        if checker is None:
            yield event.plain_result(self._t(event, "cmd.add.twitch_no_creds"))
            return

        if platform == "youtube" and channel_id.startswith("@"):
            try:
                info = await checker.validate_channel(channel_id, self._session)
            except Exception:
                info = None
            if info is None:
                yield event.plain_result(self._t(event, "cmd.check.unknown", platform=platform, channel_id=channel_id))
                return
            resolved_id = info.channel_id
        else:
            resolved_id = channel_id

        try:
            statuses = await checker.check_status([resolved_id], self._session)
        except Exception as e:
            yield event.plain_result(self._t(event, "error.generic", error=str(e)))
            return

        snap = statuses.get(resolved_id)
        if snap is None:
            yield event.plain_result(self._t(event, "cmd.check.unknown", platform=platform, channel_id=channel_id))
            return

        if snap.is_live:
            yield event.plain_result(self._t(
                event, "cmd.check.live",
                name=snap.streamer_name, platform=platform, title=snap.title,
                category=snap.category or "-", url=snap.stream_url,
            ))
        else:
            yield event.plain_result(self._t(event, "cmd.check.offline", name=snap.streamer_name, platform=platform))

    @live.command("lang")
    async def cmd_lang(self, event: AstrMessageEvent, lang: str):
        lang = lang.strip()
        if lang not in ("en", "zh-Hans", "zh-Hant"):
            yield event.plain_result(self._t(event, "cmd.lang.invalid", lang=lang))
            return

        async with self._store.lock:
            self._store.set_language(event.unified_msg_origin, lang)
            await self._store.persist()

        yield event.plain_result(self._i18n.get(lang, "cmd.lang.success", lang=lang))

    @live.command("notify")
    async def cmd_notify(self, event: AstrMessageEvent, value: str):
        value = value.lower()
        if value not in ("on", "off"):
            yield event.plain_result(self._t(event, "cmd.notify.invalid", value=value))
            return

        enabled = value == "on"
        async with self._store.lock:
            self._store.set_notify(event.unified_msg_origin, enabled)
            await self._store.persist()

        key = "cmd.notify.enabled" if enabled else "cmd.notify.disabled"
        yield event.plain_result(self._t(event, key))

    @live.command("end_notify")
    async def cmd_end_notify(self, event: AstrMessageEvent, value: str):
        value = value.lower()
        if value not in ("on", "off"):
            yield event.plain_result(self._t(event, "cmd.end_notify.invalid", value=value))
            return

        enabled = value == "on"
        async with self._store.lock:
            self._store.set_end_notify(event.unified_msg_origin, enabled)
            await self._store.persist()

        key = "cmd.end_notify.enabled" if enabled else "cmd.end_notify.disabled"
        yield event.plain_result(self._t(event, key))

    @live.command("status")
    async def cmd_status(self, event: AstrMessageEvent):
        active = sum(1 for p in self._pollers if p.healthy)
        total = len(self._pollers)

        yt = len(self._store.reverse_index.get("youtube", {}))
        tw = len(self._store.reverse_index.get("twitch", {}))
        bl = len(self._store.reverse_index.get("bilibili", {}))
        unique = yt + tw + bl
        groups = len(self._store.groups)

        lines = [
            self._t(event, "cmd.status.header"),
            self._t(event, "cmd.status.pollers", active=active, total=total),
            self._t(event, "cmd.status.monitors", yt=yt, tw=tw, bl=bl),
            self._t(event, "cmd.status.channels", count=unique),
            self._t(event, "cmd.status.groups", count=groups),
        ]
        yield event.plain_result("\n".join(lines))
