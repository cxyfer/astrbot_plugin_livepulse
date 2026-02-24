## MODIFIED Requirements

### Requirement: /live add command
The system SHALL provide `/live add <platform> <channel_id>` to add a monitor to the current group. Platform MUST be one of `youtube`, `twitch`, `bilibili`. After successful addition and persistence, the system SHALL perform a single immediate status check for the newly added channel. If the check succeeds (`StatusSnapshot.success == True`), the system SHALL update the monitor's `last_status` and set `initialized = True` before responding. If the check fails, the system SHALL keep `last_status = "unknown"` and `initialized = False`, and SHALL NOT block the add operation.

#### Scenario: Successfully add a YouTube monitor
- **WHEN** user sends `/live add youtube UCxxxxx` in a group
- **THEN** the system SHALL validate the channel exists, add it to the group's monitor list, perform a single status check, and confirm with the channel name

#### Scenario: Successfully add with @handle
- **WHEN** user sends `/live add youtube @handle`
- **THEN** the system SHALL resolve the handle to a Channel ID, add the monitor, perform a single status check, and confirm

#### Scenario: Add duplicate monitor
- **WHEN** user adds a monitor that already exists in the current group
- **THEN** the system SHALL respond that the monitor already exists (idempotent, no state change)

#### Scenario: Add monitor exceeding per-group limit
- **WHEN** the current group has reached its max monitors limit (default 30)
- **THEN** the system SHALL reject the add operation with a "group limit reached" error

#### Scenario: Add monitor exceeding global limit
- **WHEN** adding would cause the global unique channel count to exceed 500
- **THEN** the system SHALL reject with a "global limit reached" error

#### Scenario: Add monitor with invalid platform
- **WHEN** user sends `/live add tiktok xxx`
- **THEN** the system SHALL respond with an error listing valid platforms

#### Scenario: Add monitor for already-live channel
- **WHEN** the channel being added is currently live
- **AND** the immediate status check succeeds (`success == True`)
- **THEN** the system SHALL record the current status as live with `initialized = True` but SHALL NOT send a live-start notification

#### Scenario: Add monitor when platform is rate-limited
- **WHEN** user sends `/live add <platform> <channel_id>`
- **AND** the platform returns a rate-limit response during channel validation
- **THEN** the system SHALL respond with the `error.rate_limited` message including the platform name
- **AND** the system SHALL NOT respond with "channel not found"

#### Scenario: Add monitor with immediate check failure
- **WHEN** user sends `/live add <platform> <channel_id>` and the channel is valid
- **AND** the immediate status check fails (network error, parse error, or `success == False`)
- **THEN** the system SHALL keep `last_status = "unknown"` and `initialized = False`
- **AND** the add operation SHALL succeed with a confirmation message
- **AND** the poller SHALL initialize the status on its next cycle

### Requirement: /live remove command
The system SHALL provide `/live remove <platform> <identifier>` to remove a monitor from the current group. The `<identifier>` SHALL accept either a `channel_id` or a `display_id` (e.g., YouTube `@handle`). When `<identifier>` does not match any `channel_id` directly, the system SHALL look up the corresponding `channel_id` via `display_id` matching within the group's monitors for the given platform.

#### Scenario: Successfully remove a monitor by channel_id
- **WHEN** user sends `/live remove youtube UCxxxxx` and the monitor exists in the group
- **THEN** the system SHALL remove it from the group's monitor list and confirm

#### Scenario: Successfully remove a monitor by @handle
- **WHEN** user sends `/live remove youtube @handle` and a monitor with `display_id == "@handle"` exists in the group
- **THEN** the system SHALL resolve the `@handle` to the corresponding `channel_id`, remove the monitor, and confirm

#### Scenario: Remove non-existent monitor
- **WHEN** user sends `/live remove youtube UCxxxxx` and no monitor matches by `channel_id` or `display_id`
- **THEN** the system SHALL respond that the monitor was not found (idempotent, no error)

### Requirement: /live list command
The system SHALL provide `/live list` to display all monitors for the current group with their current live status using emoji markers. Each entry SHALL display `{status_emoji} {platform} | {name} ({display_id})`. The `status_emoji` SHALL be determined by: `live` -> `🟢`, `offline` -> `🔴`, `unknown` (or `initialized == False`) -> `❓`.

#### Scenario: List monitors with emoji status
- **WHEN** user sends `/live list` in a group with monitors
- **THEN** the system SHALL display each monitor's emoji status, platform, channel name, and `display_id`

#### Scenario: List empty monitors
- **WHEN** user sends `/live list` in a group with no monitors
- **THEN** the system SHALL respond that no monitors are configured

#### Scenario: List shows display_id for YouTube
- **WHEN** a YouTube monitor has `display_id = "@handle"`
- **THEN** `/live list` SHALL display `(@handle)` instead of `(UCxxxxx)`

#### Scenario: List shows channel_id as fallback
- **WHEN** a monitor has `display_id == channel_id` (Bilibili/Twitch or YouTube fallback)
- **THEN** `/live list` SHALL display `(channel_id)` as the identifier

## ADDED Requirements

### Requirement: Status emoji mapping
The system SHALL define a constant mapping from status strings to emoji symbols: `{"live": "🟢", "offline": "🔴", "unknown": "❓"}`. This mapping SHALL be the single source of truth for all status-to-emoji conversions. When `initialized == False`, the effective status SHALL be `"unknown"` regardless of `last_status`.

#### Scenario: Emoji mapping completeness
- **WHEN** any code path converts a status string to an emoji
- **THEN** it SHALL use the centralized mapping constant
- **AND** any unrecognized status value SHALL fallback to `❓`

#### Scenario: Uninitialized entry always shows unknown emoji
- **WHEN** a `MonitorEntry` has `initialized == False`
- **THEN** the displayed emoji SHALL be `❓` regardless of `last_status` value
