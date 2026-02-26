# Platform Adapters Specification

## Purpose

Define the interface and behavior requirements for platform-specific adapters that fetch live stream status from different streaming platforms.

## Requirements

### Requirement: StatusSnapshot data population

Platform adapters SHALL populate `StatusSnapshot` with platform-specific identifiers to support proper username formatting in notifications.

For **Bilibili**:
- `streamer_name`: The user's display name (`uname` from API)
- `display_id`: The numeric UID
- `login_name`: Not used (Bilibili does not have a separate login name concept)

For **Twitch**:
- `streamer_name`: The display name (`user_name` from API, preserves case)
- `display_id`: The login name (`user_login` from API, lowercase)
- `login_name`: The login name (`user_login` from API, lowercase) - used for comparison with display name

#### Scenario: Bilibili adapter populates display_id
- **WHEN** BilibiliChecker creates a StatusSnapshot
- **THEN** `display_id` SHALL be set to the UID
- **AND** `streamer_name` SHALL be set to the uname

#### Scenario: Twitch adapter populates login_name
- **WHEN** TwitchChecker creates a StatusSnapshot
- **THEN** `display_id` SHALL be set to `user_login` (lowercase)
- **AND** `login_name` SHALL be set to `user_login` (lowercase)
- **AND** `streamer_name` SHALL be set to `user_name` (original case)

### Requirement: Backward compatibility

Platform adapters SHALL remain backward compatible when new fields are added to `StatusSnapshot`. New fields SHALL have default values so existing code continues to work.

#### Scenario: Old data without login_name
- **WHEN** loading stored StatusSnapshot data that lacks `login_name`
- **THEN** the system SHALL treat `login_name` as `None`
- **AND** formatting SHALL gracefully fall back to displaying only `streamer_name`
