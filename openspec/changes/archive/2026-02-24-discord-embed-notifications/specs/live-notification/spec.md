## MODIFIED Requirements

### Requirement: Live-start notification content
The system SHALL send a notification when a monitored streamer goes live. The notification MUST include: streamer name, stream title, category (if available), stream link, and cover thumbnail image. The notification text SHALL begin with 🟢 emoji. The `notify.live_start` i18n template SHALL use 🟢 as the leading emoji across all language files.

When the notification target is a Discord platform, the system SHALL send a `DiscordEmbed` component instead of plain text. The Embed SHALL include: color `0x57F287`, title from `notify.embed.live_title` i18n key as a clickable link to `stream_url`, description set to stream title, inline field `Platform`, inline field `Category` (only if non-empty), thumbnail from `thumbnail_url` (if available), and footer set to streamer name. The `MessageChain` for Discord targets SHALL contain only the `DiscordEmbed` component — no `Comp.Plain` or `Comp.Image`.

When the notification target is NOT a Discord platform, the system SHALL use the existing plain text + image behavior unchanged.

#### Scenario: Full notification with image (non-Discord)
- **WHEN** a monitored channel transitions from offline to live
- **AND** `notify_enabled` is true for the group
- **AND** global notifications are enabled
- **AND** `StatusSnapshot.success == True`
- **AND** the target origin does NOT belong to a Discord platform adapter
- **THEN** the system SHALL send a `MessageChain` containing text (🟢, name, title, category, link) and `Comp.Image.fromURL(thumbnail_url)` to the group's `unified_msg_origin`

#### Scenario: Discord target receives Embed for live-start
- **WHEN** a monitored channel transitions from offline to live
- **AND** `notify_enabled` is true for the group
- **AND** global notifications are enabled
- **AND** `StatusSnapshot.success == True`
- **AND** the target origin belongs to a Discord platform adapter
- **AND** `DiscordEmbed` is available (import succeeded)
- **THEN** the system SHALL send a `MessageChain` containing a single `DiscordEmbed` with color `0x57F287`, title from `notify.embed.live_title`, url set to `stream_url`, description set to stream title, inline field for platform name, inline field for category (if non-empty), thumbnail set to `thumbnail_url` (if available), and footer set to streamer name

#### Scenario: Fallback to text-only on image failure
- **WHEN** the system attempts to send a notification with an image
- **AND** the image component fails (network error, invalid URL)
- **THEN** the system SHALL send a text-only notification without the image
- **AND** exactly one notification SHALL be delivered (no duplicates from retry)

#### Scenario: No notification on failed check
- **WHEN** a `StatusSnapshot` has `success == False`
- **THEN** the system SHALL NOT evaluate state transitions
- **AND** SHALL NOT send any notification

### Requirement: End-of-stream notification
The system SHALL send an end-of-stream notification when a monitored channel transitions from live to offline, if `end_notify_enabled` is true for the group. The notification text SHALL begin with 🔴 emoji. The `notify.live_end` i18n template SHALL use 🔴 as the leading emoji across all language files.

When the notification target is a Discord platform, the system SHALL send a `DiscordEmbed` component. The Embed SHALL include: color `0x95A5A6`, title from `notify.embed.end_title` i18n key, inline field `Platform`, and footer set to streamer name. The `MessageChain` for Discord targets SHALL contain only the `DiscordEmbed` component.

When the notification target is NOT a Discord platform, the system SHALL use the existing plain text behavior unchanged.

#### Scenario: End notification sent (non-Discord)
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is true for the group
- **AND** global end notifications are enabled
- **AND** `StatusSnapshot.success == True`
- **AND** the target origin does NOT belong to a Discord platform adapter
- **THEN** the system SHALL send an end-of-stream notification with 🔴 emoji and the streamer name

#### Scenario: Discord target receives Embed for live-end
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is true for the group
- **AND** global end notifications are enabled
- **AND** `StatusSnapshot.success == True`
- **AND** the target origin belongs to a Discord platform adapter
- **AND** `DiscordEmbed` is available (import succeeded)
- **THEN** the system SHALL send a `MessageChain` containing a single `DiscordEmbed` with color `0x95A5A6`, title from `notify.embed.end_title`, inline field for platform name, and footer set to streamer name

#### Scenario: End notification disabled
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is false for the group
- **THEN** the system SHALL NOT send an end-of-stream notification

## ADDED Requirements

### Requirement: Discord platform detection from origin
The system SHALL detect whether a notification target is a Discord platform by extracting the `platform_id` prefix from `unified_msg_origin` (first segment before `:`), resolving the platform instance via `Context.get_platform_inst(platform_id)`, and checking `meta().name == "discord"`.

#### Scenario: Origin belongs to Discord adapter
- **WHEN** `origin` starts with a `platform_id` that resolves to a platform instance with `meta().name == "discord"`
- **THEN** `_is_discord_origin(origin)` SHALL return `True`

#### Scenario: Origin belongs to non-Discord adapter
- **WHEN** `origin` starts with a `platform_id` that resolves to a platform instance with `meta().name != "discord"`
- **THEN** `_is_discord_origin(origin)` SHALL return `False`

#### Scenario: Origin platform instance not found
- **WHEN** `origin` starts with a `platform_id` that does not resolve to any platform instance
- **THEN** `_is_discord_origin(origin)` SHALL return `False`

### Requirement: Graceful fallback when DiscordEmbed unavailable
The `DiscordEmbed` class SHALL be imported at module level with a `try/except ImportError` guard. If the import fails, `DiscordEmbed` SHALL be set to `None`. When `DiscordEmbed is None`, all notification targets SHALL use the existing plain text format regardless of platform. No error SHALL be raised.

#### Scenario: DiscordEmbed import fails
- **WHEN** the plugin cannot import `DiscordEmbed` from `astrbot.core.platform.sources.discord.components`
- **THEN** `DiscordEmbed` SHALL be `None`
- **AND** all notifications SHALL use the existing plain text format
- **AND** no error SHALL be raised during plugin initialization or notification delivery

#### Scenario: Embed construction fails at runtime
- **WHEN** `DiscordEmbed` is available but construction raises an exception (e.g. `TypeError` from signature change)
- **THEN** the system SHALL catch the exception, log a debug message, and fall back to plain text delivery for that notification

### Requirement: Embed i18n keys
New i18n keys SHALL be added to all three language files (`en.json`, `zh-Hans.json`, `zh-Hant.json`) for Embed-specific text. Existing `notify.live_start` and `notify.live_end` keys SHALL remain unchanged.

| Key | en | zh-Hans | zh-Hant |
|-----|----|---------|---------|
| `notify.embed.live_title` | `🟢 Now LIVE!` | `🟢 直播开始！` | `🟢 直播開始！` |
| `notify.embed.end_title` | `🔴 Stream Ended` | `🔴 直播结束` | `🔴 直播結束` |
| `notify.embed.field.platform` | `Platform` | `平台` | `平台` |
| `notify.embed.field.category` | `Category` | `分区` | `分類` |

#### Scenario: All locale files contain new keys
- **WHEN** the plugin loads i18n files
- **THEN** each of `en.json`, `zh-Hans.json`, `zh-Hant.json` SHALL contain keys `notify.embed.live_title`, `notify.embed.end_title`, `notify.embed.field.platform`, `notify.embed.field.category`
- **AND** existing keys `notify.live_start` and `notify.live_end` SHALL remain unchanged in all files
