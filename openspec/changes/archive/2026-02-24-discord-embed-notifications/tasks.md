## 1. Guarded Import & Platform Detection

- [x] 1.1 Add module-level `try/except ImportError` for `DiscordEmbed` in `core/notifier.py`, setting `DiscordEmbed = None` on failure
- [x] 1.2 Add `_is_discord_origin(self, origin: str) -> bool` method: extract `platform_id` via `origin.split(":", 1)[0]`, call `self._ctx.get_platform_inst(platform_id)`, return `True` only if `inst is not None and inst.meta().name == "discord"`

## 2. i18n Keys

- [x] 2.1 Add `notify.embed.live_title`, `notify.embed.end_title`, `notify.embed.field.platform`, `notify.embed.field.category` to `i18n/en.json`
- [x] 2.2 Add the same 4 keys to `i18n/zh-Hans.json` with Simplified Chinese values
- [x] 2.3 Add the same 4 keys to `i18n/zh-Hant.json` with Traditional Chinese values

## 3. Embed Builders

- [x] 3.1 Add `_build_live_embed(self, lang: str, platform: str, snapshot: StatusSnapshot) -> MessageChain` in `Notifier`: construct `DiscordEmbed` with color `0x57F287`, title from `notify.embed.live_title`, url from `snapshot.stream_url`, description from `snapshot.title`, inline Platform field, inline Category field (if non-empty), thumbnail from `snapshot.thumbnail_url` (if available), footer from `snapshot.streamer_name`
- [x] 3.2 Add `_build_end_embed(self, lang: str, platform: str, streamer_name: str) -> MessageChain` in `Notifier`: construct `DiscordEmbed` with color `0x95A5A6`, title from `notify.embed.end_title`, inline Platform field, footer from `streamer_name`

## 4. Delivery Refactor

- [x] 4.1 Extract `_send_chain(self, origin: str, chain: MessageChain) -> None` from `_deliver`: call `send_message`, check return value (`False` → increment failure), handle exceptions with failure tracking
- [x] 4.2 Refactor `_deliver` to use `_send_chain` for both image+text and text-only paths

## 5. Notification Branching

- [x] 5.1 Modify `send_live_notification`: if `DiscordEmbed is not None` and `_is_discord_origin(origin)`, build embed via `_build_live_embed` wrapped in `try/except Exception` (fallback to plain text on failure), send via `_send_chain`; otherwise use existing `_deliver`
- [x] 5.2 Modify `send_end_notification`: same branching pattern using `_build_end_embed`
