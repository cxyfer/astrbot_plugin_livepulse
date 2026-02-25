## ADDED Requirements

### Requirement: Unrecognized URL error message
When the auto-detect path receives a URL that does not match any supported platform pattern in `_HOST_PLATFORM_MAP`, the system SHALL respond with a dedicated error message using the `cmd.add.unrecognized_url` i18n key. The message SHALL list the supported URL domains.

This error is ONLY triggered when:
1. `channel_id` is empty (single-arg mode)
2. `_detect_platform` returns `None` (host not in allowlist)
3. The input contains both `.` and `/` (URL heuristic)

If the host IS in the allowlist but the checker's URL regex does not match (e.g., `youtube.com/` with no channel path), the error SHALL be `cmd.add.invalid_channel` instead (C6).

#### Scenario: Unrecognized URL shows supported formats
- **WHEN** user sends `/live add https://unknown-site.com/foo`
- **THEN** the system SHALL respond with `cmd.add.unrecognized_url`
- **AND** the message SHALL mention `youtube.com`, `twitch.tv`, and `live.bilibili.com`

#### Scenario: i18n key exists in all locales
- **WHEN** the i18n system looks up `cmd.add.unrecognized_url`
- **THEN** the key SHALL exist in `en.json`, `zh-Hans.json`, and `zh-Hant.json`
- **AND** all three locale messages SHALL have identical placeholder sets (no format string mismatch)

#### Scenario: Non-URL invalid input uses existing error
- **WHEN** user sends `/live add tiktok someuser` (invalid platform, not a URL)
- **THEN** the system SHALL respond with `cmd.add.invalid_platform` (NOT `cmd.add.unrecognized_url`)

#### Scenario: Valid host but invalid path uses invalid_channel
- **WHEN** user sends `/live add youtube.com/` (valid host, no channel path)
- **THEN** the system SHALL respond with `cmd.add.invalid_channel` (NOT `cmd.add.unrecognized_url`) (C6)

#### Scenario: Platform name without channel_id uses invalid_channel
- **WHEN** user sends `/live add youtube` (valid platform name, no channel_id)
- **THEN** the system SHALL respond with `cmd.add.invalid_channel` (NOT `cmd.add.unrecognized_url`)
