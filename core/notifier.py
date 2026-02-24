from __future__ import annotations

from typing import TYPE_CHECKING

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import MessageChain

from core.models import StatusSnapshot, Transition

if TYPE_CHECKING:
    from astrbot.api.star import Context

    from core.store import Store
    from i18n import I18nManager


class Notifier:
    def __init__(self, context: Context, store: Store, i18n: I18nManager, include_thumbnail: bool = True) -> None:
        self._ctx = context
        self._store = store
        self._i18n = i18n
        self._include_thumbnail = include_thumbnail

    async def send_live_notification(
        self,
        origin: str,
        platform: str,
        snapshot: StatusSnapshot,
        global_enable: bool,
    ) -> None:
        if not self._should_notify(origin, global_enable, Transition.LIVE_START):
            return
        lang = self._store.get_language(origin)
        text = self._i18n.get(
            lang,
            "notify.live_start",
            name=snapshot.streamer_name,
            platform=platform,
            title=snapshot.title,
            category=snapshot.category or "",
            url=snapshot.stream_url,
        )
        await self._deliver(origin, text, snapshot.thumbnail_url)

    async def send_end_notification(
        self,
        origin: str,
        platform: str,
        streamer_name: str,
        global_enable: bool,
        global_end_enable: bool,
    ) -> None:
        if not self._should_notify(origin, global_enable, Transition.LIVE_END, global_end_enable):
            return
        lang = self._store.get_language(origin)
        text = self._i18n.get(lang, "notify.live_end", name=streamer_name, platform=platform)
        await self._deliver(origin, text, thumbnail_url="")

    def _should_notify(
        self,
        origin: str,
        global_enable: bool,
        transition: Transition,
        global_end_enable: bool = True,
    ) -> bool:
        if not global_enable:
            return False
        gs = self._store.get_group(origin)
        if gs is None or not gs.notify_enabled:
            return False
        if transition == Transition.LIVE_END and (not global_end_enable or not gs.end_notify_enabled):
            return False
        return True

    async def _deliver(self, origin: str, text: str, thumbnail_url: str) -> None:
        if self._include_thumbnail and thumbnail_url:
            chain = MessageChain(chain=[Comp.Plain(text), Comp.Image.fromURL(thumbnail_url)])
            try:
                await self._ctx.send_message(origin, chain)
                self._store.reset_failure(origin)
                return
            except Exception:
                logger.debug(f"Image send failed for {origin}, falling back to text-only")

        chain = MessageChain(chain=[Comp.Plain(text)])
        try:
            await self._ctx.send_message(origin, chain)
            self._store.reset_failure(origin)
        except Exception as e:
            count = self._store.increment_failure(origin)
            logger.warning(f"Notification delivery failed for {origin} ({count} consecutive): {e}")
