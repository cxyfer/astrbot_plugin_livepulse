## ADDED Requirements

### Requirement: WebUI configuration via _conf_schema.json
The system SHALL provide a `_conf_schema.json` file for WebUI configuration. Configuration SHALL be injected via `AstrBotConfig` in `__init__`.

#### Scenario: Plugin loads with config
- **WHEN** the plugin is instantiated by AstrBot
- **THEN** configuration values from WebUI SHALL be available via `self.config`

### Requirement: Twitch credentials configuration
The system SHALL provide `twitch_client_id` (string) and `twitch_client_secret` (string) configuration fields.

#### Scenario: Twitch credentials provided
- **WHEN** both `twitch_client_id` and `twitch_client_secret` are non-empty
- **THEN** the Twitch poller SHALL start and authenticate using Client Credentials flow

#### Scenario: Twitch credentials missing
- **WHEN** either field is empty
- **THEN** the Twitch poller SHALL NOT start

### Requirement: Default polling intervals configuration
The system SHALL provide per-platform polling interval fields: `youtube_interval` (int, default 300), `twitch_interval` (int, default 120), `bilibili_interval` (int, default 180). Values are in seconds.

#### Scenario: Custom interval applied
- **WHEN** an administrator sets `youtube_interval` to 600
- **THEN** the YouTube poller SHALL poll every 600 seconds

### Requirement: Default language configuration
The system SHALL provide `default_language` (string, options: `en`/`zh`, default `en`).

#### Scenario: Default language setting
- **WHEN** `default_language` is set to `zh`
- **THEN** new groups SHALL default to Chinese language

### Requirement: Max monitors per group configuration
The system SHALL provide `max_monitors_per_group` (int, default 30).

#### Scenario: Limit enforced
- **WHEN** a group reaches `max_monitors_per_group`
- **THEN** additional `/live add` commands SHALL be rejected

### Requirement: Global max unique channels configuration
The system SHALL provide `max_global_channels` (int, default 500).

#### Scenario: Global limit enforced
- **WHEN** the total unique channel count across all groups reaches `max_global_channels`
- **THEN** additional `/live add` commands for new channels SHALL be rejected

### Requirement: Global notification toggles
The system SHALL provide `enable_notifications` (bool, default true) and `enable_end_notifications` (bool, default true).

#### Scenario: Global notifications disabled
- **WHEN** `enable_notifications` is false
- **THEN** no live-start notifications SHALL be sent to any group

#### Scenario: Global end notifications disabled
- **WHEN** `enable_end_notifications` is false
- **THEN** no end-of-stream notifications SHALL be sent to any group

### Requirement: Cover thumbnail toggle
The system SHALL provide `include_thumbnail` (bool, default true).

#### Scenario: Thumbnail disabled
- **WHEN** `include_thumbnail` is false
- **THEN** notifications SHALL be sent as text-only without cover images

### Requirement: HTTP timeout configuration
The system SHALL provide per-platform timeout fields: `youtube_timeout` (int, default 20), `twitch_timeout` (int, default 10), `bilibili_timeout` (int, default 10). Values are in seconds.

#### Scenario: Custom timeout applied
- **WHEN** `youtube_timeout` is set to 30
- **THEN** YouTube HTTP requests SHALL use a 30-second timeout
