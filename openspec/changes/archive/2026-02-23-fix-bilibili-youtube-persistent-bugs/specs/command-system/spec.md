## MODIFIED Requirements

### Requirement: /live add command
The system SHALL provide `/live add <platform> <channel_id>` to add a monitor to the current group. Platform MUST be one of `youtube`, `twitch`, `bilibili`.

#### Scenario: Successfully add a YouTube monitor
- **WHEN** user sends `/live add youtube UCxxxxx` in a group
- **THEN** the system SHALL validate the channel exists, add it to the group's monitor list, and confirm with the channel name

#### Scenario: Successfully add with @handle
- **WHEN** user sends `/live add youtube @handle`
- **THEN** the system SHALL resolve the handle to a Channel ID, add the monitor, and confirm

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
- **THEN** the system SHALL record the current status as live but SHALL NOT send a live-start notification

#### Scenario: Add monitor when platform is rate-limited
- **WHEN** user sends `/live add <platform> <channel_id>`
- **AND** the platform returns a rate-limit response during channel validation
- **THEN** the system SHALL respond with the `error.rate_limited` message including the platform name
- **AND** the system SHALL NOT respond with "channel not found"
