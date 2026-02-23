## ADDED Requirements

### Requirement: Live-start notification content
The system SHALL send a notification when a monitored streamer goes live. The notification MUST include: streamer name, stream title, category (if available), stream link, and cover thumbnail image.

#### Scenario: Full notification with image
- **WHEN** a monitored channel transitions from offline to live
- **AND** `notify_enabled` is true for the group
- **AND** global notifications are enabled
- **THEN** the system SHALL send a `MessageChain` containing text (name, title, category, link) and `Comp.Image.fromURL(thumbnail_url)` to the group's `unified_msg_origin`

#### Scenario: Fallback to text-only on image failure
- **WHEN** the system attempts to send a notification with an image
- **AND** the image component fails (network error, invalid URL)
- **THEN** the system SHALL send a text-only notification without the image
- **AND** exactly one notification SHALL be delivered (no duplicates from retry)

### Requirement: No duplicate notifications per live session
The system SHALL track live session identity per monitor per group and ensure at most one live-start notification per session.

#### Scenario: Poller detects same live session twice
- **WHEN** a channel remains live across consecutive poll cycles
- **THEN** the system SHALL NOT send additional live-start notifications

#### Scenario: Channel goes offline then live again (new session)
- **WHEN** a channel goes offline and then goes live again
- **THEN** the system SHALL send a new live-start notification (new session)

### Requirement: End-of-stream notification
The system SHALL send an end-of-stream notification when a monitored channel transitions from live to offline, if `end_notify_enabled` is true for the group.

#### Scenario: End notification sent
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is true for the group
- **AND** global end notifications are enabled
- **THEN** the system SHALL send an end-of-stream notification with the streamer name

#### Scenario: End notification disabled
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is false for the group
- **THEN** the system SHALL NOT send an end-of-stream notification

### Requirement: First-observation suppression
On first startup or when adding a monitor that is already live, the system SHALL NOT send a live-start notification. This prevents notification spam.

#### Scenario: Plugin startup with already-live channel
- **WHEN** the plugin starts and a monitored channel is already live
- **THEN** the system SHALL record the status as live but SHALL NOT send a notification

#### Scenario: Adding a monitor for a live channel
- **WHEN** a user adds a monitor for a channel that is currently live
- **THEN** the system SHALL record the status as live but SHALL NOT send a notification

### Requirement: Notification effective rule
Effective notification delivery MUST satisfy: `global_notify_enabled AND group_notify_enabled`. Both conditions MUST be true for any notification to be sent.

#### Scenario: Global notifications disabled
- **WHEN** global notifications are disabled in WebUI
- **THEN** no notifications SHALL be sent to any group regardless of per-group settings

#### Scenario: Group notifications disabled
- **WHEN** a group's `notify_enabled` is false
- **THEN** no notifications SHALL be sent to that group regardless of global settings

### Requirement: Auto-disable on delivery failure
The system SHALL track consecutive notification delivery failures per group. After 10 consecutive failures, the system SHALL automatically disable notifications for that group (set `notify_enabled = false`). The failure counter resets on any successful send or when the user runs `/live notify on`.

#### Scenario: Auto-disable after 10 failures
- **WHEN** `send_message` fails 10 consecutive times for a group
- **THEN** the system SHALL set `notify_enabled = false` for that group
- **AND** SHALL log the auto-disable event with the group origin

#### Scenario: Counter reset on success
- **WHEN** a notification is successfully sent to a group
- **THEN** the failure counter for that group SHALL reset to 0

#### Scenario: Manual re-enable after auto-disable
- **WHEN** a user sends `/live notify on` in an auto-disabled group
- **THEN** the system SHALL re-enable notifications and reset the failure counter to 0
