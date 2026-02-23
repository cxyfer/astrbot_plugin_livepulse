# command-system Specification

## Purpose
TBD - created by archiving change livepulse-plugin. Update Purpose after archive.
## Requirements
### Requirement: Command group /live with sub-commands
The system SHALL register a command group `/live` using AstrBot's `@filter.command_group("live")` decorator. All sub-commands SHALL be registered under this group.

#### Scenario: User invokes /live without sub-command
- **WHEN** a user sends `/live` without a sub-command
- **THEN** AstrBot SHALL render the command group tree structure showing all available sub-commands

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

### Requirement: /live remove command
The system SHALL provide `/live remove <platform> <channel_id>` to remove a monitor from the current group.

#### Scenario: Successfully remove a monitor
- **WHEN** user sends `/live remove youtube UCxxxxx` and the monitor exists in the group
- **THEN** the system SHALL remove it from the group's monitor list and confirm

#### Scenario: Remove non-existent monitor
- **WHEN** user sends `/live remove youtube UCxxxxx` and the monitor does not exist in the group
- **THEN** the system SHALL respond that the monitor was not found (idempotent, no error)

### Requirement: /live list command
The system SHALL provide `/live list` to display all monitors for the current group with their current live status.

#### Scenario: List monitors with status
- **WHEN** user sends `/live list` in a group with monitors
- **THEN** the system SHALL display each monitor's platform, channel name, and current status (live/offline)

#### Scenario: List empty monitors
- **WHEN** user sends `/live list` in a group with no monitors
- **THEN** the system SHALL respond that no monitors are configured

### Requirement: /live check command
The system SHALL provide `/live check <platform> <channel_id>` to perform a one-off status check without requiring a subscription.

#### Scenario: Check a live channel
- **WHEN** user sends `/live check twitch shroud` and the channel is live
- **THEN** the system SHALL display stream title, category, and link

#### Scenario: Check an offline channel
- **WHEN** user sends `/live check bilibili 12345` and the user is offline
- **THEN** the system SHALL display that the user is not streaming

#### Scenario: Check does not modify state
- **WHEN** user sends `/live check` for any channel
- **THEN** no subscription data or persistent state SHALL be modified

### Requirement: /live lang command
The system SHALL provide `/live lang <en|zh>` to switch the response language for the current group.

#### Scenario: Switch language to Chinese
- **WHEN** user sends `/live lang zh`
- **THEN** all subsequent responses and notifications for this group SHALL use Chinese strings

#### Scenario: Switch language to English
- **WHEN** user sends `/live lang en`
- **THEN** all subsequent responses and notifications for this group SHALL use English strings

#### Scenario: Invalid language code
- **WHEN** user sends `/live lang jp`
- **THEN** the system SHALL respond with an error listing valid language codes (en, zh)

### Requirement: /live notify command
The system SHALL provide `/live notify <on|off>` to toggle live-start notifications for the current group.

#### Scenario: Disable notifications
- **WHEN** user sends `/live notify off`
- **THEN** the system SHALL stop sending live-start notifications to this group
- **AND** the group's monitors SHALL continue being polled (status tracked)

#### Scenario: Enable notifications
- **WHEN** user sends `/live notify on`
- **THEN** the system SHALL resume sending live-start notifications to this group
- **AND** the send failure counter SHALL reset to 0

### Requirement: /live end_notify command
The system SHALL provide `/live end_notify <on|off>` to toggle end-of-stream notifications for the current group.

#### Scenario: Disable end notifications
- **WHEN** user sends `/live end_notify off`
- **THEN** the system SHALL stop sending end-of-stream notifications to this group

#### Scenario: Enable end notifications
- **WHEN** user sends `/live end_notify on`
- **THEN** the system SHALL resume sending end-of-stream notifications to this group

### Requirement: /live status command
The system SHALL provide `/live status` to display plugin health information.

#### Scenario: Display plugin status
- **WHEN** user sends `/live status`
- **THEN** the system SHALL display: number of active poller tasks, per-platform monitor counts, total unique channels, total groups, and whether each poller is healthy

