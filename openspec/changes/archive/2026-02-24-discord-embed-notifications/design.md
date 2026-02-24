## Context

Live notifications are currently sent as `Comp.Plain` + optional `Comp.Image` via `Notifier._deliver()`. AstrBot's Discord adapter supports `DiscordEmbed` component in `MessageChain`, converting it to `discord.Embed` internally. The plugin needs to branch notification rendering by target platform without affecting non-Discord targets.

Key API surface (verified from AstrBot source):
- `Context.get_platform_inst(platform_id) -> Platform | None`
- `Platform.meta().name` returns adapter name (e.g. `"discord"`)
- `DiscordEmbed(title, description, color, url, thumbnail, image, footer, fields)` — no `timestamp` parameter
- `unified_msg_origin` format: `{platform_id}:{message_type}:{session_id}`

## Goals / Non-Goals

**Goals:**
- Discord targets receive rich Embed notifications (live-start and live-end)
- Non-Discord targets retain identical plain text behavior (zero regression)
- Graceful degradation when Discord adapter is not installed
- i18n support for all Embed-specific text

**Non-Goals:**
- Embed `timestamp` field (DiscordEmbed API does not expose it)
- Rich notification support for other platforms (Telegram, Slack, etc.)
- Strategy/Renderer abstraction layer — YAGNI for single-platform enhancement
- New configuration options — Discord detection is automatic

## Decisions

### D1: Simple branching in Notifier (over Strategy pattern)

Add `_is_discord_origin()`, `_build_live_embed()`, `_build_end_embed()` as private methods in `Notifier`. Branch in `send_live_notification` / `send_end_notification` before calling `_deliver`.

**Why**: Single-platform enhancement. Strategy abstraction adds files/indirection with no current benefit. If future platforms need rich embeds, refactor then.

### D2: Platform detection via `get_platform_inst()` + `meta().name`

```python
platform_id = origin.split(":", 1)[0]
inst = self._ctx.get_platform_inst(platform_id)
return inst is not None and inst.meta().name == "discord"
```

**Why**: ID-based lookup supports multiple Discord bot instances. Avoids deprecated `get_platform()` type-based API. Aligns with `send_message` routing (also ID-based). Fails closed — unknown origin → plain text.

### D3: Module-level guarded import

```python
try:
    from astrbot.core.platform.sources.discord.components import DiscordEmbed
except ImportError:
    DiscordEmbed = None
```

**Why**: `DiscordEmbed` is internal API (`astrbot.core.*`), not in `astrbot.api`. Import may fail if Discord adapter is not installed. Setting `None` allows a simple `if DiscordEmbed is not None` guard.

### D4: Embed construction wrapped in try/except

Catch `Exception` during embed build → fall back to plain text path. Protects against constructor signature drift in future AstrBot versions.

### D5: Shared `_send_chain()` for delivery

Extract common `send_message` + failure tracking logic from `_deliver` into `_send_chain(origin, chain)`. Both embed and plain text paths use it. Check `send_message` return value — `False` means no matching platform, treated as delivery failure.

### D6: i18n key namespace `notify.embed.*`

New keys (added to all 3 locale files):

| Key | en | zh-Hans | zh-Hant |
|-----|----|---------|---------|
| `notify.embed.live_title` | `🟢 Now LIVE!` | `🟢 直播开始！` | `🟢 直播開始！` |
| `notify.embed.end_title` | `🔴 Stream Ended` | `🔴 直播结束` | `🔴 直播結束` |
| `notify.embed.field.platform` | `Platform` | `平台` | `平台` |
| `notify.embed.field.category` | `Category` | `分区` | `分類` |

Existing `notify.live_start` / `notify.live_end` remain unchanged for non-Discord fallback.

### D7: Timestamp omitted

`DiscordEmbed` constructor has no `timestamp` parameter and `to_discord_embed()` does not set it. Plugin cannot post-process the `discord.Embed` object (conversion happens inside adapter). Accepted as API limitation.

## Risks / Trade-offs

| Risk | Severity | Mitigation |
|------|----------|------------|
| `DiscordEmbed` import path changes in future AstrBot | High | Module-level `try/except`; all Discord logic gated on `DiscordEmbed is not None` |
| Constructor signature drift (`TypeError`) | Medium | `try/except Exception` around embed build → plain text fallback |
| `send_message` returns `False` silently | Medium | `_send_chain` checks return value, increments failure counter on `False` |
| `origin` format changes | Low | `split(":", 1)[0]` is minimal parsing; fails closed to plain text |
| Notifier grows platform-specific logic over time | Low | Acceptable for single platform; refactor to Strategy if 2+ platforms need rich embeds |
