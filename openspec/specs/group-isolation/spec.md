# group-isolation Specification

## Purpose
TBD - created by archiving change livepulse-plugin. Update Purpose after archive.
## Requirements
### Requirement: Per-group monitor lists
Monitor lists SHALL be fully isolated per group, keyed by `unified_msg_origin`. Each group independently manages its own set of monitored channels.

#### Scenario: Group A's monitors invisible to Group B
- **WHEN** Group A adds a YouTube monitor
- **AND** Group B sends `/live list`
- **THEN** Group B's list SHALL NOT include Group A's monitor

#### Scenario: Same channel in multiple groups
- **WHEN** both Group A and Group B add the same YouTube channel
- **THEN** each group SHALL have its own independent subscription entry
- **AND** removing the monitor in Group A SHALL NOT affect Group B's subscription

### Requirement: Per-group language setting
Language setting SHALL be isolated per group. Changing language in one group SHALL NOT affect any other group.

#### Scenario: Independent language settings
- **WHEN** Group A sets language to `zh` and Group B sets language to `en`
- **THEN** Group A's responses and notifications SHALL use Chinese
- **AND** Group B's responses and notifications SHALL use English

### Requirement: Per-group notification toggles
Notification toggles (`notify_enabled`, `end_notify_enabled`) SHALL be isolated per group.

#### Scenario: Independent notify toggles
- **WHEN** Group A disables notifications and Group B has notifications enabled
- **AND** a shared monitored channel goes live
- **THEN** only Group B SHALL receive the notification

### Requirement: Per-group last_status tracking
Each group SHALL maintain independent `last_status` and session tracking for its monitors, even when multiple groups monitor the same channel.

#### Scenario: Independent status tracking for shared channel
- **WHEN** Group A and Group B both monitor the same Twitch channel
- **AND** Group A was added before the channel went live
- **AND** Group B was added while the channel was already live
- **THEN** Group A SHALL receive the live-start notification
- **AND** Group B SHALL NOT receive the live-start notification (first-observation suppression)

