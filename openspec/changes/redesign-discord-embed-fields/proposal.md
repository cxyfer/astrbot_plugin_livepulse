# Proposal: Redesign Discord Embed Fields

## Context

Current Discord Embed notifications display minimal structure:
- **Live start**: title as "🟢 Now LIVE!", stream title in description, streamer name in footer, only Platform and Category fields.
- **Live end**: title as "🔴 Stream Ended", empty description, streamer name in footer, only Platform field.

The layout lacks visual separation and emoji decoration, making it feel flat and uninformative.

## Goal

Restructure both live-start and live-end Embed layouts to use Discord Embed Fields with emoji prefixes, improving readability and visual appeal.

## User Decisions (Captured)

| Decision | Choice |
|----------|--------|
| Field layout mode | **Mixed**: stream title on its own line, Platform & Category inline side-by-side |
| Streamer name placement | **Move to Embed title** (e.g., "🟢 StreamerName is LIVE!") |
| Live-end embed content | **Add more Fields** (expand beyond just Platform) |
| Stream link handling | **Add dedicated link Field** with 🔗 emoji |

## Requirements

### R1: Live-Start Embed Redesign

- **Title**: Merge streamer name into title → `"🟢 {name} is LIVE!"` (i18n-ized)
- **Description**: Stream title (unchanged)
- **URL**: Stream URL on title (unchanged)
- **Color**: Green 0x57F287 (unchanged)
- **Thumbnail**: Channel thumbnail (unchanged)
- **Footer**: Remove streamer name, leave empty or omit
- **Fields**:
  1. `📡 Platform` — inline: true
  2. `🎮 Category` — inline: true (conditional: only if category is non-empty)
  3. `🔗 Link` — inline: false, value = stream URL

### R2: Live-End Embed Redesign

- **Title**: Merge streamer name into title → `"🔴 {name} Stream Ended"` (i18n-ized)
- **Description**: Empty (unchanged)
- **Color**: Grey 0x95A5A6 (unchanged)
- **Footer**: Remove streamer name, leave empty or omit
- **Fields**:
  1. `📡 Platform` — inline: true

### R3: i18n Updates

All new/modified user-visible strings must be added to all three locale files (en, zh-Hans, zh-Hant):
- `notify.embed.live_title`: Change from static text to template with `{name}` placeholder
- `notify.embed.end_title`: Change from static text to template with `{name}` placeholder
- `notify.embed.field.platform`: Add emoji prefix `📡`
- `notify.embed.field.category`: Add emoji prefix `🎮`
- New key `notify.embed.field.link`: Add with emoji prefix `🔗`

### R4: Backward Compatibility

- Plain-text fallback notifications (non-Discord) must remain unchanged.
- The `_make_embed` bypass mechanism for Pydantic v1 must be preserved.
- `send_end_notification` signature receives `streamer_name` as a parameter — this must be passed to `_build_end_embed` for use in the title.

## Constraints

### Hard Constraints

- **DiscordEmbed attributes**: Only `title`, `description`, `color`, `url`, `thumbnail`, `image`, `footer`, `fields` are supported. No `author`, `timestamp`, or `footer icon_url`.
- **Fields format**: Each field is `{"name": str, "value": str, "inline": bool}`.
- **Pydantic v1 bypass**: Must continue using `__new__` + `object.__setattr__` pattern in `_make_embed`.
- **i18n system**: All visible strings go through `I18nManager.get()` with f-string-style `{placeholder}` templates.

### Soft Constraints

- Emoji selection should be visually intuitive and consistent across locales.
- Field names (with emoji) stored in i18n files, not hardcoded in Python.

## Affected Files

| File | Change |
|------|--------|
| `core/notifier.py` | Refactor `_build_live_embed` and `_build_end_embed` |
| `i18n/en.json` | Update/add embed string keys |
| `i18n/zh-Hant.json` | Update/add embed string keys |
| `i18n/zh-Hans.json` | Update/add embed string keys |

## Success Criteria

1. Live-start Embed shows streamer name in title, has Platform (inline), Category (inline, conditional), and Link (full-width) Fields with emoji prefixes.
2. Live-end Embed shows streamer name in title, has Platform (inline) Field with emoji prefix.
3. All three locale files contain the updated/new i18n keys.
4. Plain-text fallback path is unaffected.
5. `test_notify` command produces the redesigned Embed on Discord.
