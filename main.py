from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import aiohttp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# Ensure plugin root is on sys.path for relative imports
_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from core.batch import (
    MAX_BATCH_SIZE,
    BatchResult,
    detect_mode,
    preprocess,
    process_batch_add,
    process_batch_remove,
)
from core.models import STATUS_EMOJI, StatusSnapshot
from core.notifier import Notifier
from core.persistence import PersistenceManager
from core.poller import PlatformPoller
from core.store import Store
from i18n import I18nManager
from platforms.bilibili import BilibiliChecker
from platforms.twitch import TwitchChecker
from platforms.youtube import YouTubeChecker

_VALID_PLATFORMS = ("youtube", "twitch", "bilibili")
_HOST_PLATFORM_MAP: dict[str, str] = {
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "m.youtube.com": "youtube",
    "twitch.tv": "twitch",
    "www.twitch.tv": "twitch",
    "m.twitch.tv": "twitch",
    "live.bilibili.com": "bilibili",
}


def _detect_platform(raw: str) -> str | None:
    url = raw if "://" in raw else f"https://{raw}"
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    if host is None:
        return None
    return _HOST_PLATFORM_MAP.get(host.lower())


_LEGACY_DATA_PATH = Path.home() / ".astrbot" / "livepulse"


def _migrate_legacy_data(new_dir: Path) -> None:
    """One-time migration: move data from legacy ~/.astrbot/livepulse/ to official plugin_data convention."""
    if new_dir.exists() or not _LEGACY_DATA_PATH.exists():
        return
    shutil.move(str(_LEGACY_DATA_PATH), str(new_dir))
    logger.info(f"Migrated plugin data: {_LEGACY_DATA_PATH} → {new_dir}")


@register(
    "astrbot_plugin_livepulse", "Xyfer", "Multi-platform live stream monitor", "1.1.4"
)
class LivePulsePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None) -> None:
        super().__init__(context)
        self.config = config or {}

        data_dir = Path(get_astrbot_data_path()) / "plugin_data" / self.name
        _migrate_legacy_data(data_dir)
        self._persistence = PersistenceManager(data_dir)
        self._i18n = I18nManager(_PLUGIN_DIR / "i18n")
        self._store = Store(
            self._persistence, default_language=config.get("default_language", "en")
        )

        self._checkers: dict[str, YouTubeChecker | TwitchChecker | BilibiliChecker] = {}
        self._pollers: list[PlatformPoller] = []
        self._poller_tasks: list[asyncio.Task] = []
        self._session: aiohttp.ClientSession | None = None
        self._notifier: Notifier | None = None
        self._bg_tasks: set[asyncio.Task] = set()
        self._initialized = False
        self._terminated = False

    # --- lifecycle ---

    async def initialize(self) -> None:
        if self._initialized:
            return

        data = self._persistence.load()
        self._store.load(data)

        try:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                }
            )

            self._checkers["youtube"] = YouTubeChecker(
                timeout=self.config.get("youtube_timeout", 20)
            )
            self._checkers["bilibili"] = BilibiliChecker(
                timeout=self.config.get("bilibili_timeout", 10)
            )

            client_id = self.config.get("twitch_client_id", "")
            client_secret = self.config.get("twitch_client_secret", "")
            if client_id and client_secret:
                self._checkers["twitch"] = TwitchChecker(
                    client_id, client_secret, timeout=self.config.get("twitch_timeout", 10)
                )

            notifier = Notifier(
                self.context,
                self._store,
                self._i18n,
                include_thumbnail=self.config.get("include_thumbnail", True),
            )
            self._notifier = notifier

            self._global_notify = self.config.get("enable_notifications", True)
            self._global_end_notify = self.config.get("enable_end_notifications", True)
            global_notify = self._global_notify
            global_end_notify = self._global_end_notify

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

            self._initialized = True
            logger.info(f"LivePulse initialized: {len(self._pollers)} pollers started")
        except Exception:
            for task in self._poller_tasks:
                task.cancel()
            for task in self._poller_tasks:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            if self._session and not self._session.closed:
                await self._session.close()
            self._pollers.clear()
            self._poller_tasks.clear()
            self._checkers.clear()
            self._session = None
            self._notifier = None
            raise

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

        for task in self._bg_tasks:
            task.cancel()
        for task in list(self._bg_tasks):
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._bg_tasks.clear()

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

    def _get_checker(
        self, platform: str
    ) -> YouTubeChecker | TwitchChecker | BilibiliChecker | None:
        return self._checkers.get(platform)

    def _st(self, event: AstrMessageEvent, value: bool) -> str:
        return self._t(event, "common.on" if value else "common.off")

    def _parse_batch_args(self, event: AstrMessageEvent, subcommand: str) -> list[str]:
        raw = event.message_str.strip()
        prefix = f"live {subcommand}"
        for p in (f"/{prefix}", prefix):
            if raw.lower().startswith(p):
                raw = raw[len(p) :].strip()
                break
        return raw.split() if raw else []

    def _format_batch_response(
        self,
        event: AstrMessageEvent,
        result: BatchResult,
        op: str,
        max_per_group: int,
        max_global: int,
    ) -> str:
        success = sum(1 for r in result.items if r.status in ("success", "removed"))
        fail = len(result.items) - success
        summary_key = (
            "cmd.batch.summary_add" if op == "add" else "cmd.batch.summary_remove"
        )
        lines = [self._t(event, summary_key, success=success, fail=fail)]

        for r in result.items:
            if r.status == "success" and r.info:
                lines.append(
                    self._t(
                        event,
                        "cmd.batch.item_success",
                        platform=r.info.platform,
                        name=r.info.channel_name,
                        channel_id=r.info.channel_id,
                    )
                )
            elif r.status == "removed":
                lines.append(
                    self._t(
                        event,
                        "cmd.batch.item_removed",
                        platform=r.platform,
                        identifier=r.identifier,
                    )
                )
            elif r.status == "duplicate":
                lines.append(
                    self._t(event, "cmd.batch.item_duplicate", identifier=r.identifier)
                )
            elif r.status == "not_found":
                lines.append(
                    self._t(event, "cmd.batch.item_not_found", identifier=r.identifier)
                )
            elif r.status == "limit_group":
                lines.append(
                    self._t(
                        event,
                        "cmd.batch.item_limit_group",
                        identifier=r.identifier,
                        limit=max_per_group,
                    )
                )
            elif r.status == "limit_global":
                lines.append(
                    self._t(
                        event,
                        "cmd.batch.item_limit_global",
                        identifier=r.identifier,
                        limit=max_global,
                    )
                )
            elif r.status in ("rate_limited", "internal_error"):
                reason = (
                    "rate limited" if r.status == "rate_limited" else "internal error"
                )
                lines.append(
                    self._t(
                        event,
                        "cmd.batch.item_fail",
                        identifier=r.identifier,
                        reason=reason,
                    )
                )

        if result.truncated > 0:
            lines.append(
                self._t(
                    event,
                    "cmd.batch.truncated",
                    count=result.truncated,
                    max=MAX_BATCH_SIZE,
                )
            )

        return "\n".join(lines)

    # --- commands ---

    @filter.command_group("live")
    def live(self):
        pass

    @live.command("add")
    async def cmd_add(
        self, event: AstrMessageEvent, platform: str = "", channel_id: str = ""
    ):
        origin = event.unified_msg_origin
        raw_args = self._parse_batch_args(event, "add")
        if not raw_args:
            yield event.plain_result(
                self._t(event, "cmd.add.invalid_platform", platform="")
            )
            return

        try:
            mode, items = detect_mode(raw_args, _VALID_PLATFORMS, _detect_platform)
        except ValueError as e:
            if str(e) == "mixed_mode":
                yield event.plain_result(self._t(event, "cmd.batch.mixed_mode"))
            elif str(e) == "no_ids":
                yield event.plain_result(
                    self._t(event, "cmd.add.invalid_channel", channel_id=raw_args[0])
                )
            else:
                raw = raw_args[0]
                if "." in raw and "/" in raw:
                    yield event.plain_result(self._t(event, "cmd.add.unrecognized_url"))
                elif raw.lower() in _VALID_PLATFORMS:
                    yield event.plain_result(
                        self._t(event, "cmd.add.invalid_channel", channel_id=raw)
                    )
                else:
                    yield event.plain_result(
                        self._t(event, "cmd.add.invalid_platform", platform=raw)
                    )
            return

        items, truncated = preprocess(items)
        if not items:
            yield event.plain_result(
                self._t(event, "cmd.add.invalid_channel", channel_id=raw_args[0])
            )
            return

        for item in items:
            if self._get_checker(item.platform) is None:
                yield event.plain_result(self._t(event, "cmd.add.twitch_no_creds"))
                return

        max_per_group = self.config.get("max_monitors_per_group", 30)
        max_global = self.config.get("max_global_channels", 500)

        result = await process_batch_add(
            self._store,
            origin,
            items,
            self._checkers,
            self._session,
            max_per_group,
            max_global,
        )
        result.truncated = truncated
        yield event.plain_result(
            self._format_batch_response(event, result, "add", max_per_group, max_global)
        )

    @live.command("remove")
    async def cmd_remove(
        self, event: AstrMessageEvent, platform: str = "", channel_id: str = ""
    ):
        origin = event.unified_msg_origin
        raw_args = self._parse_batch_args(event, "remove")
        if not raw_args:
            yield event.plain_result(
                self._t(event, "cmd.add.invalid_platform", platform="")
            )
            return

        try:
            mode, items = detect_mode(raw_args, _VALID_PLATFORMS, _detect_platform)
        except ValueError as e:
            if str(e) == "mixed_mode":
                yield event.plain_result(self._t(event, "cmd.batch.mixed_mode"))
            elif str(e) == "no_ids":
                yield event.plain_result(
                    self._t(
                        event,
                        "cmd.remove.missing_channel",
                        platform=raw_args[0].lower(),
                    )
                )
            else:
                raw = raw_args[0]
                if raw.lower() in _VALID_PLATFORMS:
                    yield event.plain_result(
                        self._t(
                            event, "cmd.remove.missing_channel", platform=raw.lower()
                        )
                    )
                elif "." in raw and "/" in raw:
                    yield event.plain_result(self._t(event, "cmd.add.unrecognized_url"))
                else:
                    yield event.plain_result(
                        self._t(
                            event, "cmd.remove.not_found", platform=raw, channel_id=raw
                        )
                    )
            return

        items, truncated = preprocess(items)
        if not items:
            yield event.plain_result(
                self._t(
                    event, "cmd.remove.missing_channel", platform=raw_args[0].lower()
                )
            )
            return

        result = await process_batch_remove(
            self._store,
            origin,
            items,
            self._checkers,
            self._session,
        )
        result.truncated = truncated
        yield event.plain_result(
            self._format_batch_response(event, result, "remove", 0, 0)
        )

    @live.command("list")
    async def cmd_list(self, event: AstrMessageEvent):
        origin = event.unified_msg_origin
        gs = self._store.get_group(origin)
        if gs is None or not any(gs.monitors.values()):
            yield event.plain_result(self._t(event, "cmd.list.empty"))
            return

        lines = [self._t(event, "cmd.list.header")]
        sections = []
        for platform in _VALID_PLATFORMS:
            entries = gs.monitors.get(platform)
            if not entries:
                continue
            section = [self._t(event, "cmd.list.platform_header", platform=platform)]
            for entry in entries.values():
                status = entry.last_status if entry.initialized else "unknown"
                emoji = STATUS_EMOJI.get(status, "❓")
                try:
                    did = (
                        unquote(entry.display_id, errors="strict")
                        if entry.display_id
                        else entry.display_id
                    )
                except Exception:
                    did = entry.display_id
                section.append(
                    self._t(
                        event,
                        "cmd.list.entry",
                        status_emoji=emoji,
                        name=entry.channel_name,
                        display_id=did,
                    )
                )
            sections.append("\n".join(section))
        lines.append("\n\n".join(sections))
        yield event.plain_result("\n".join(lines))

    @live.command("check")
    async def cmd_check(self, event: AstrMessageEvent, platform: str, channel_id: str):
        platform = platform.lower()
        if platform not in _VALID_PLATFORMS:
            yield event.plain_result(
                self._t(event, "cmd.add.invalid_platform", platform=platform)
            )
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
                yield event.plain_result(
                    self._t(
                        event,
                        "cmd.check.unknown",
                        platform=platform,
                        channel_id=channel_id,
                    )
                )
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
            yield event.plain_result(
                self._t(
                    event, "cmd.check.unknown", platform=platform, channel_id=channel_id
                )
            )
            return

        if snap.is_live:
            yield event.plain_result(
                self._t(
                    event,
                    "cmd.check.live",
                    name=snap.streamer_name,
                    platform=platform,
                    title=snap.title,
                    category=snap.category or "-",
                    url=snap.stream_url,
                )
            )
        else:
            yield event.plain_result(
                self._t(
                    event,
                    "cmd.check.offline",
                    name=snap.streamer_name,
                    platform=platform,
                )
            )

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
    async def cmd_notify(self, event: AstrMessageEvent):
        raw_args = self._parse_batch_args(event, "notify")
        arg = raw_args[0] if raw_args else None

        if arg is None:
            origin = event.unified_msg_origin
            gs = self._store.get_group(origin)
            group_on = gs.notify_enabled if gs else True
            failures = gs.send_failure_count if gs else 0
            effective = self._global_notify and group_on
            yield event.plain_result(
                self._t(
                    event,
                    "cmd.notify.status",
                    global_st=self._st(event, self._global_notify),
                    group_st=self._st(event, group_on),
                    failures=failures,
                    effective=self._st(event, effective),
                )
            )
            return

        arg = arg.lower()
        if arg not in ("on", "off"):
            yield event.plain_result(self._t(event, "cmd.notify.invalid", value=arg))
            return

        enabled = arg == "on"
        async with self._store.lock:
            self._store.set_notify(event.unified_msg_origin, enabled)
            await self._store.persist()

        key = "cmd.notify.enabled" if enabled else "cmd.notify.disabled"
        yield event.plain_result(self._t(event, key))

    @live.command("end_notify")
    async def cmd_end_notify(self, event: AstrMessageEvent):
        raw_args = self._parse_batch_args(event, "end_notify")
        arg = raw_args[0] if raw_args else None

        if arg is None:
            origin = event.unified_msg_origin
            gs = self._store.get_group(origin)
            group_notify = gs.notify_enabled if gs else True
            group_end = gs.end_notify_enabled if gs else True
            notify_effective = self._global_notify and group_notify
            effective = notify_effective and self._global_end_notify and group_end
            yield event.plain_result(
                self._t(
                    event,
                    "cmd.end_notify.status",
                    global_st=self._st(event, self._global_end_notify),
                    group_st=self._st(event, group_end),
                    notify_st=self._st(event, notify_effective),
                    effective=self._st(event, effective),
                )
            )
            return

        arg = arg.lower()
        if arg not in ("on", "off"):
            yield event.plain_result(
                self._t(event, "cmd.end_notify.invalid", value=arg)
            )
            return

        enabled = arg == "on"
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

        origin = event.unified_msg_origin
        gs = self._store.get_group(origin)
        group_notify = gs.notify_enabled if gs else True
        group_end = gs.end_notify_enabled if gs else True
        notify_eff = self._global_notify and group_notify
        end_eff = notify_eff and self._global_end_notify and group_end
        lines.append(
            self._t(
                event,
                "cmd.status.notify_summary",
                notify_st=self._st(event, notify_eff),
                end_st=self._st(event, end_eff),
            )
        )
        yield event.plain_result("\n".join(lines))

    @live.command("test_notify")
    async def cmd_test_notify(self, event: AstrMessageEvent, delay: str | None = None):
        if self._notifier is None:
            yield event.plain_result(self._t(event, "cmd.test_notify.not_ready"))
            return

        if delay is None:
            yield event.plain_result(self._t(event, "cmd.test_notify.invalid_delay"))
            return

        try:
            delay_int = int(delay)
        except (ValueError, TypeError):
            yield event.plain_result(self._t(event, "cmd.test_notify.invalid_delay"))
            return

        if delay_int <= 0:
            yield event.plain_result(self._t(event, "cmd.test_notify.invalid_delay"))
            return

        if delay_int > 300:
            yield event.plain_result(
                self._t(event, "cmd.test_notify.delay_too_long", max=300)
            )
            return

        origin = event.unified_msg_origin
        if any(
            t.get_name() == f"test_notify:{origin}" and not t.done()
            for t in self._bg_tasks
        ):
            yield event.plain_result(self._t(event, "cmd.test_notify.already_pending"))
            return

        task = asyncio.create_task(
            self._run_test_notify(origin, delay_int), name=f"test_notify:{origin}"
        )
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        yield event.plain_result(
            self._t(event, "cmd.test_notify.scheduled", delay=delay_int)
        )

    async def _run_test_notify(self, origin: str, delay: int) -> None:
        try:
            await asyncio.sleep(delay)
            snapshot = StatusSnapshot(
                is_live=True,
                streamer_name="Test Streamer",
                title="Test Stream Title",
                category="Just Chatting",
                stream_url="https://example.com/test",
                thumbnail_url="https://placehold.co/1280x720/orange/white?text=LivePulse+Test",
                display_id="TestStreamer",
            )
            await self._notifier.send_live_notification(
                origin, "test", snapshot, global_enable=True, force=True
            )
            await asyncio.sleep(1)
            await self._notifier.send_end_notification(
                origin,
                "test",
                "Test Streamer",
                global_enable=True,
                global_end_enable=True,
                display_id="TestStreamer",
                force=True,
            )
        except asyncio.CancelledError:
            logger.info(f"test_notify task cancelled for {origin}")
            raise
        except Exception as e:
            logger.error(f"test_notify task failed for {origin}: {e}", exc_info=True)
