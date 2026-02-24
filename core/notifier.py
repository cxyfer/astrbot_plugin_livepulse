from __future__ import annotations

from typing import TYPE_CHECKING

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import MessageChain

from core.models import StatusSnapshot, Transition

try:
    from astrbot.core.platform.sources.discord.components import DiscordEmbed
except ImportError:
    DiscordEmbed = None

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
        *,
        force: bool = False,
    ) -> None:
        if not force and not self._should_notify(origin, global_enable, Transition.LIVE_START):
            return
        track = not force
        lang = self._store.get_language(origin)
        if DiscordEmbed is not None and self._is_discord_origin(origin):
            try:
                chain = self._build_live_embed(lang, platform, snapshot)
                await self._send_chain(origin, chain, track_failure=track)
                return
            except Exception:
                logger.debug(f"Embed build failed for {origin}, falling back to plain text")
        text = self._i18n.get(
            lang,
            "notify.live_start",
            name=snapshot.streamer_name,
            platform=platform,
            title=snapshot.title,
            category=snapshot.category or "",
            url=snapshot.stream_url,
        )
        await self._deliver(origin, text, snapshot.thumbnail_url, track_failure=track)

    async def send_end_notification(
        self,
        origin: str,
        platform: str,
        streamer_name: str,
        global_enable: bool,
        global_end_enable: bool,
        *,
        force: bool = False,
    ) -> None:
        if not force and not self._should_notify(origin, global_enable, Transition.LIVE_END, global_end_enable):
            return
        track = not force
        lang = self._store.get_language(origin)
        if DiscordEmbed is not None and self._is_discord_origin(origin):
            try:
                chain = self._build_end_embed(lang, platform, streamer_name)
                await self._send_chain(origin, chain, track_failure=track)
                return
            except Exception:
                logger.debug(f"Embed build failed for {origin}, falling back to plain text")
        text = self._i18n.get(lang, "notify.live_end", name=streamer_name, platform=platform)
        await self._deliver(origin, text, thumbnail_url="", track_failure=track)

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

    async def _deliver(self, origin: str, text: str, thumbnail_url: str, *, track_failure: bool = True) -> None:
        if self._include_thumbnail and thumbnail_url:
            chain = MessageChain(chain=[Comp.Plain(text), Comp.Image.fromURL(thumbnail_url)])
            if await self._send_chain(origin, chain, track_failure=track_failure):
                return
            logger.debug(f"Image send failed for {origin}, falling back to text-only")

        await self._send_chain(origin, MessageChain(chain=[Comp.Plain(text)]), track_failure=track_failure)

    async def _send_chain(self, origin: str, chain: MessageChain, *, track_failure: bool = True) -> bool:
        try:
            result = await self._ctx.send_message(origin, chain)
            if result is False:
                if track_failure:
                    count = self._store.increment_failure(origin)
                    logger.warning(f"Notification delivery returned False for {origin} ({count} consecutive)")
                else:
                    logger.warning(f"Notification delivery returned False for {origin} (forced/test)")
                return False
            if track_failure:
                self._store.reset_failure(origin)
            return True
        except Exception as e:
            if track_failure:
                count = self._store.increment_failure(origin)
                logger.warning(f"Notification delivery failed for {origin} ({count} consecutive): {e}")
            else:
                logger.error(f"Notification delivery failed for {origin} (forced/test): {e}")
            return False

    def _is_discord_origin(self, origin: str) -> bool:
        platform_id = origin.split(":", 1)[0]
        inst = self._ctx.get_platform_inst(platform_id)
        return inst is not None and inst.meta().name == "discord"

    @staticmethod
    def _make_embed(**kwargs: object) -> DiscordEmbed:
        embed = DiscordEmbed.__new__(DiscordEmbed)
        object.__setattr__(embed, "type", "discord_embed")
        for k, v in kwargs.items():
            object.__setattr__(embed, k, v)
        return embed

    def _build_live_embed(self, lang: str, platform: str, snapshot: StatusSnapshot) -> MessageChain:
        fields = [{"name": self._i18n.get(lang, "notify.embed.field.platform"), "value": platform, "inline": True}]
        if snapshot.category:
            fields.append({"name": self._i18n.get(lang, "notify.embed.field.category"), "value": snapshot.category, "inline": True})
        embed = self._make_embed(
            title=self._i18n.get(lang, "notify.embed.live_title"),
            description=snapshot.title,
            color=0x57F287,
            url=snapshot.stream_url,
            thumbnail=snapshot.thumbnail_url or None,
            image=None,
            footer=snapshot.streamer_name,
            fields=fields,
        )
        return MessageChain(chain=[embed])

    def _build_end_embed(self, lang: str, platform: str, streamer_name: str) -> MessageChain:
        fields = [{"name": self._i18n.get(lang, "notify.embed.field.platform"), "value": platform, "inline": True}]
        embed = self._make_embed(
            title=self._i18n.get(lang, "notify.embed.end_title"),
            description="",
            color=0x95A5A6,
            url="",
            thumbnail=None,
            image=None,
            footer=streamer_name,
            fields=fields,
        )
        return MessageChain(chain=[embed])
