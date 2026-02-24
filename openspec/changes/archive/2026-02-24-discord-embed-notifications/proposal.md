# discord-embed-notifications

## Context

Currently, live-start and live-end notifications are sent as plain text (`Comp.Plain`) with an optional thumbnail image (`Comp.Image.fromURL`). This applies uniformly to all platforms (Discord, QQ, Telegram, etc.).

AstrBot's Discord adapter natively supports `DiscordEmbed` component (`astrbot.core.platform.sources.discord.components.DiscordEmbed`). The adapter's `_parse_to_discord()` method already handles `DiscordEmbed` instances in `MessageChain`, converting them to `discord.Embed` objects. This enables rich embed notifications for Discord targets without any framework modification.

The `unified_msg_origin` format is `{platform_id}:{message_type}:{session_id}`, which allows platform detection by extracting the platform_id prefix.

## Requirements

### Requirement: Discord Embed for live-start notification

When the notification target is a Discord platform, the system SHALL send a rich Embed instead of plain text for live-start notifications.

The Embed SHALL include:
- **Color**: `0x57F287` (Discord green)
- **Title**: Localized live-start heading (e.g. "🟢 直播開始！") as a clickable link to `stream_url`
- **Description**: Stream title
- **Fields**: `Platform` (inline), `Category` (inline, only if non-empty)
- **Thumbnail**: `thumbnail_url` (if available)
- **Footer**: Streamer name
- **Timestamp**: Current UTC time

#### Scenario: Discord target receives Embed

- **WHEN** a live-start notification is triggered
- **AND** the target `origin` belongs to a Discord platform adapter
- **THEN** the system SHALL build a `MessageChain` containing a `DiscordEmbed` component
- **AND** SHALL NOT include `Comp.Plain` or `Comp.Image` in the same chain

#### Scenario: Non-Discord target receives plain text

- **WHEN** a live-start notification is triggered
- **AND** the target `origin` does NOT belong to a Discord platform adapter
- **THEN** the system SHALL use the existing plain text + image behavior unchanged

### Requirement: Discord Embed for live-end notification

When the notification target is a Discord platform, the system SHALL send a rich Embed for live-end notifications.

The Embed SHALL include:
- **Color**: `0x95A5A6` (grey)
- **Title**: Localized live-end heading (e.g. "🔴 直播結束")
- **Footer**: Streamer name
- **Fields**: `Platform` (inline)
- **Timestamp**: Current UTC time

#### Scenario: Discord target receives end Embed

- **WHEN** a live-end notification is triggered
- **AND** the target `origin` belongs to a Discord platform adapter
- **THEN** the system SHALL build a `MessageChain` containing a `DiscordEmbed` component

### Requirement: Graceful fallback when DiscordEmbed unavailable

The `DiscordEmbed` class is in `astrbot.core.platform.sources.discord.components`, which is NOT part of the public API. If the import fails (e.g. Discord adapter not installed), the system SHALL fall back to plain text for all targets.

#### Scenario: DiscordEmbed import fails

- **WHEN** the plugin cannot import `DiscordEmbed`
- **THEN** all notifications SHALL use the existing plain text format
- **AND** no error SHALL be raised

### Requirement: Platform detection from origin

The system SHALL detect whether a notification target is a Discord platform by extracting the `platform_id` prefix from `unified_msg_origin` and matching it against registered Discord adapter instance IDs via `Context`.

#### Scenario: Origin belongs to Discord

- **WHEN** `origin` starts with a platform_id that corresponds to a Discord adapter
- **THEN** `_is_discord_origin()` SHALL return `True`

### Requirement: i18n keys for Embed content

New i18n keys SHALL be added for Embed-specific text (titles, field labels) across all three language files (en, zh-Hans, zh-Hant). Existing `notify.live_start` and `notify.live_end` keys SHALL remain unchanged for non-Discord fallback.

## Constraints

| Type | Constraint |
|------|-----------|
| Hard | `DiscordEmbed` is NOT in `astrbot.api` — must use try/except import |
| Hard | Non-Discord platforms cannot render `DiscordEmbed` — must branch by platform |
| Hard | `unified_msg_origin` format: `{platform_id}:{message_type}:{session_id}` |
| Hard | `DiscordEmbed.fields` expects `list[dict]` with keys `name`, `value`, `inline` |
| Hard | Live-end notification has no `title`, `category`, `thumbnail_url`, or `stream_url` data |
| Soft | Existing plain text behavior must remain identical for non-Discord targets |
| Soft | No new config options — auto-detect Discord from origin |

## Success Criteria

1. Discord targets receive rich Embed notifications with color, title, fields, thumbnail, and timestamp
2. Non-Discord targets receive identical plain text notifications as before (zero regression)
3. Plugin loads and functions correctly even when Discord adapter is not installed
4. All three i18n language files contain the new Embed-specific keys
