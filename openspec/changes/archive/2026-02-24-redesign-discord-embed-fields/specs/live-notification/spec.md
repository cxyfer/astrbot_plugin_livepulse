## MODIFIED Requirements

### Requirement: Live-start notification content
The system SHALL send a notification when a monitored streamer goes live. The notification MUST include: streamer name, stream title, category (if available), stream link, and cover thumbnail image. The notification text SHALL begin with 🟢 emoji. The `notify.live_start` i18n template SHALL use 🟢 as the leading emoji across all language files.

When the notification target is a Discord platform, the system SHALL send a `DiscordEmbed` component instead of plain text. The Embed SHALL include:
- **title**: Rendered from `notify.embed.live_title` i18n key with `{name}` placeholder substituted by `streamer_name`. The streamer name SHALL be truncated with trailing `…` if the resulting title would exceed 256 characters.
- **color**: `0x57F287`
- **url**: `stream_url` (clickable title link)
- **description**: Stream title
- **thumbnail**: `thumbnail_url` (if available)
- **footer**: Rendered from `notify.embed.footer` i18n key with `{name}` and `{id}` placeholders. `{name}` is `streamer_name`, `{id}` is `display_id` (falls back to `channel_id` when `display_id` is empty).
- **fields** (in fixed order):
  1. `📡`-prefixed platform name — `inline: true` — always present
  2. `🎮`-prefixed category — `inline: true` — present only if `category.strip()` is non-empty
  3. `🔗`-prefixed link — `inline: false` — present only if `stream_url.strip()` is non-empty, value is raw URL

The `MessageChain` for Discord targets SHALL contain only the `DiscordEmbed` component — no `Comp.Plain` or `Comp.Image`.

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
- **THEN** the system SHALL send a `MessageChain` containing a single `DiscordEmbed` with color `0x57F287`, title from `notify.embed.live_title` with `{name}` replaced by `streamer_name`, url set to `stream_url`, description set to stream title, inline `📡`-prefixed field for platform name, inline `🎮`-prefixed field for category (if `category.strip()` is non-empty), non-inline `🔗`-prefixed field for stream URL (if `stream_url.strip()` is non-empty), thumbnail set to `thumbnail_url` (if available), and footer from `notify.embed.footer` with `{name}` and `{id}` replaced

#### Scenario: Discord live-start embed with long streamer name
- **WHEN** a streamer name combined with the i18n title template exceeds 256 characters
- **THEN** the system SHALL truncate the streamer name portion and append `…` so that the final title length is exactly 256 characters
- **AND** the footer SHALL display the full (untruncated) streamer name and ID

#### Scenario: Discord live-start embed without category
- **WHEN** `snapshot.category` is empty or whitespace-only
- **THEN** the embed SHALL contain only Platform and Link fields (no Category field)

#### Scenario: Discord live-start embed without stream URL
- **WHEN** `snapshot.stream_url` is empty or whitespace-only
- **THEN** the embed SHALL omit the Link field
- **AND** the embed `url` attribute SHALL be set to `None`

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

When the notification target is a Discord platform, the system SHALL send a `DiscordEmbed` component. The Embed SHALL include:
- **title**: Rendered from `notify.embed.end_title` i18n key with `{name}` placeholder substituted by `streamer_name`. Truncation rules identical to live-start.
- **color**: `0x95A5A6`
- **footer**: Rendered from `notify.embed.footer` i18n key with `{name}` and `{id}` placeholders, same logic as live-start.
- **fields**: Exactly 1 field — `📡`-prefixed platform name, `inline: true`.

The `MessageChain` for Discord targets SHALL contain only the `DiscordEmbed` component.

The `send_end_notification` method SHALL accept a `display_id: str` parameter in addition to the existing `streamer_name` parameter. The caller (PlatformPoller) SHALL pass `snapshot.display_id` for this value. When `display_id` is empty or `None`, the footer SHALL fall back to showing only `streamer_name`.

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
- **THEN** the system SHALL send a `MessageChain` containing a single `DiscordEmbed` with color `0x95A5A6`, title from `notify.embed.end_title` with `{name}` replaced by `streamer_name`, exactly 1 inline `📡`-prefixed field for platform name, and footer from `notify.embed.footer` with `{name}` and `{id}` replaced

#### Scenario: Discord live-end embed with long streamer name
- **WHEN** a streamer name combined with the end title template exceeds 256 characters
- **THEN** the system SHALL truncate the streamer name portion and append `…` so that the final title length is exactly 256 characters

#### Scenario: End notification disabled
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is false for the group
- **THEN** the system SHALL NOT send an end-of-stream notification

### Requirement: Embed i18n keys
The following i18n keys SHALL be present in all three language files (`en.json`, `zh-Hans.json`, `zh-Hant.json`). Title keys SHALL use `{name}` placeholder for streamer name substitution. Field name keys SHALL include emoji prefixes. A new `notify.embed.footer` key SHALL use `{name}` and `{id}` placeholders. A new `notify.embed.field.link` key SHALL be added.

Existing `notify.live_start` and `notify.live_end` plain-text keys SHALL remain unchanged.

| Key | en | zh-Hans | zh-Hant |
|-----|----|---------|---------|
| `notify.embed.live_title` | `🟢 {name} is LIVE!` | `🟢 {name} 直播开始！` | `🟢 {name} 直播開始！` |
| `notify.embed.end_title` | `🔴 {name} Stream Ended` | `🔴 {name} 直播结束` | `🔴 {name} 直播結束` |
| `notify.embed.footer` | `{name}（@{id}）` | `{name}（@{id}）` | `{name}（@{id}）` |
| `notify.embed.field.platform` | `📡 Platform` | `📡 平台` | `📡 平台` |
| `notify.embed.field.category` | `🎮 Category` | `🎮 分区` | `🎮 分類` |
| `notify.embed.field.link` | `🔗 Link` | `🔗 链接` | `🔗 連結` |

#### Scenario: All locale files contain updated and new keys
- **WHEN** the plugin loads i18n files
- **THEN** each of `en.json`, `zh-Hans.json`, `zh-Hant.json` SHALL contain keys `notify.embed.live_title`, `notify.embed.end_title`, `notify.embed.footer`, `notify.embed.field.platform`, `notify.embed.field.category`, `notify.embed.field.link`
- **AND** `notify.embed.live_title` and `notify.embed.end_title` SHALL contain the `{name}` placeholder in all locales
- **AND** `notify.embed.footer` SHALL contain both `{name}` and `{id}` placeholders in all locales
- **AND** existing keys `notify.live_start` and `notify.live_end` SHALL remain unchanged in all files

#### Scenario: Title i18n template renders correctly
- **WHEN** `I18nManager.get(locale, "notify.embed.live_title", name="TestStreamer")` is called for any supported locale
- **THEN** the result SHALL contain the substring `TestStreamer`

## ADDED Requirements

### Requirement: Title truncation protection
The system SHALL ensure that Discord Embed titles never exceed the 256-character limit imposed by the Discord API. When the i18n-rendered title (with streamer name substituted) would exceed 256 characters, the system SHALL truncate the `streamer_name` portion only and append a single `…` character, preserving the template prefix and suffix intact.

The truncation budget for the name SHALL be computed as: `256 - len(template_rendered_with_empty_name)`, where the template is rendered with `name=""` to measure the fixed portion. If the streamer name exceeds this budget, it SHALL be sliced to `budget - 1` characters with `…` appended.

#### Scenario: Normal-length streamer name
- **WHEN** `streamer_name` is `"TestStreamer"` (11 chars)
- **AND** the title template fixed portion is 15 chars
- **THEN** the title SHALL be rendered without truncation
- **AND** `len(title) <= 256`

#### Scenario: Extremely long streamer name
- **WHEN** `streamer_name` is 300 characters long
- **AND** the title template fixed portion is 15 chars
- **THEN** the name SHALL be truncated to 240 characters + `…`
- **AND** the final title SHALL be exactly 256 characters
- **AND** the title SHALL end with the template suffix (e.g., `" is LIVE!"`)

#### Scenario: Truncation is idempotent
- **WHEN** the same (locale, streamer_name) input is processed twice
- **THEN** both invocations SHALL produce identical title strings

### Requirement: send_end_notification display_id parameter
The `send_end_notification` method SHALL accept an additional `display_id: str` keyword parameter with default value `""`. This parameter SHALL be passed through to `_build_end_embed` for footer rendering.

The `_PendingNotification` dataclass SHALL include a `display_id: str` field. The PlatformPoller SHALL populate this field with `entry.display_id` (from `MonitorEntry`, which defaults to `channel_id` via `__post_init__`). This ensures the display_id is available even when the offline snapshot does not carry it.

The PlatformPoller SHALL pass `note.display_id` when calling `send_end_notification`.

The `test_notify` command SHALL pass `display_id="TestStreamer"` when calling `send_end_notification`.

#### Scenario: Poller passes display_id to end notification
- **WHEN** a LIVE_END transition is detected
- **THEN** the poller SHALL call `send_end_notification` with `display_id=note.display_id` where `note.display_id` was populated from `entry.display_id`

#### Scenario: test_notify passes display_id
- **WHEN** the test_notify command sends an end notification
- **THEN** it SHALL pass `display_id="TestStreamer"` to `send_end_notification`

#### Scenario: display_id is empty
- **WHEN** `display_id` is `""` or `None`
- **THEN** the footer SHALL render with `{id}` substituted by `streamer_name` as the final fallback
- **NOTE** In practice, `MonitorEntry.display_id` defaults to `channel_id` via `__post_init__`, so `display_id` will nearly always be non-empty. This fallback exists for defensive correctness.
