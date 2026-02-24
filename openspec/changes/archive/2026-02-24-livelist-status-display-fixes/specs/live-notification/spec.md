## MODIFIED Requirements

### Requirement: Live-start notification content
The system SHALL send a notification when a monitored streamer goes live. The notification MUST include: streamer name, stream title, category (if available), stream link, and cover thumbnail image. The notification text SHALL begin with 🟢 emoji. The `notify.live_start` i18n template SHALL use 🟢 as the leading emoji across all language files.

#### Scenario: Full notification with image
- **WHEN** a monitored channel transitions from offline to live
- **AND** `notify_enabled` is true for the group
- **AND** global notifications are enabled
- **AND** `StatusSnapshot.success == True`
- **THEN** the system SHALL send a `MessageChain` containing text (🟢, name, title, category, link) and `Comp.Image.fromURL(thumbnail_url)` to the group's `unified_msg_origin`

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

#### Scenario: End notification sent
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is true for the group
- **AND** global end notifications are enabled
- **AND** `StatusSnapshot.success == True`
- **THEN** the system SHALL send an end-of-stream notification with 🔴 emoji and the streamer name

#### Scenario: End notification disabled
- **WHEN** a channel transitions from live to offline
- **AND** `end_notify_enabled` is false for the group
- **THEN** the system SHALL NOT send an end-of-stream notification

### Requirement: First-observation suppression
On first startup or when adding a monitor that is already live, the system SHALL NOT send a live-start notification. This prevents notification spam. The immediate status check performed by `/live add` SHALL set `initialized = True` on success, which means the poller's first observation will see an initialized entry and correctly detect transitions rather than treating the first poll as a "first observation."

#### Scenario: Plugin startup with already-live channel
- **WHEN** the plugin starts and a monitored channel is already live
- **THEN** the system SHALL record the status as live but SHALL NOT send a notification

#### Scenario: Adding a monitor for a live channel
- **WHEN** a user adds a monitor for a channel that is currently live
- **AND** the immediate check succeeds (`success == True`)
- **THEN** the system SHALL record the status as live with `initialized = True` but SHALL NOT send a notification

#### Scenario: Adding a monitor when immediate check fails
- **WHEN** a user adds a monitor for a channel and the immediate check fails
- **THEN** the monitor SHALL remain `initialized = False`
- **AND** the poller's first successful observation SHALL apply first-observation suppression as normal
