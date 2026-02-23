# polling-architecture Specification

## Purpose
TBD - created by archiving change livepulse-plugin. Update Purpose after archive.
## Requirements
### Requirement: Per-platform independent poller tasks
The system SHALL run one `asyncio.Task` per platform (YouTube, Twitch, Bilibili). Each task operates independently with its own polling interval and error handling.

#### Scenario: Independent platform tasks
- **WHEN** the plugin initializes
- **THEN** the system SHALL create separate asyncio tasks for youtube_poller, twitch_poller, and bilibili_poller

#### Scenario: One poller crash does not affect others
- **WHEN** the YouTube poller encounters an unrecoverable error
- **THEN** the Twitch and Bilibili pollers SHALL continue running unaffected
- **AND** the YouTube poller SHALL be restarted automatically

### Requirement: Cross-group channel deduplication
Each poller SHALL aggregate all unique channel IDs across all groups for its platform and query each channel at most once per cycle. Results SHALL be fanned out to all subscribing groups.

#### Scenario: Deduplicated query
- **WHEN** Group A and Group B both monitor the same Twitch channel
- **THEN** the Twitch poller SHALL make only one API call for that channel per cycle
- **AND** both groups SHALL receive the status update

#### Scenario: Per-group fanout
- **WHEN** a channel's status changes from offline to live
- **THEN** the system SHALL evaluate notification rules independently for each subscribing group
- **AND** send notifications only to groups with `notify_enabled = true`

### Requirement: Poller cycle workflow
Each poller cycle SHALL follow this sequence: (1) take immutable snapshot of monitor mapping, (2) deduplicate channel IDs, (3) fetch statuses, (4) compute transitions per group, (5) dispatch notifications, (6) update state, (7) persist changes, (8) sleep for configured interval.

#### Scenario: Snapshot-based polling
- **WHEN** a poller begins a cycle
- **THEN** it SHALL take a snapshot of the current monitor state
- **AND** any modifications during the cycle (add/remove) SHALL NOT affect the current cycle

### Requirement: Poller auto-restart on failure
If a platform poller task crashes due to an unrecoverable error, the system SHALL automatically restart it after a delay.

#### Scenario: Poller restart
- **WHEN** a poller task exits unexpectedly (not due to cancellation)
- **THEN** the system SHALL log the error and restart the task
- **AND** the restart delay SHALL use exponential backoff (base=30s, multiplier=2, max=300s)

#### Scenario: Graceful cancellation
- **WHEN** a poller task is cancelled (via `terminate()`)
- **THEN** the system SHALL NOT attempt to restart it

### Requirement: Persistence with atomic writes
The system SHALL persist state to `~/.astrbot/livepulse/data.json` using atomic writes (write to temp file, then `os.replace`). All writes SHALL go through a single writer to prevent corruption.

#### Scenario: Atomic write
- **WHEN** state needs to be persisted
- **THEN** the system SHALL write to a temporary file first and atomically replace the target file

#### Scenario: Concurrent write protection
- **WHEN** multiple events trigger persistence simultaneously (poller update + command handler)
- **THEN** the single writer SHALL serialize the writes to prevent data corruption

#### Scenario: Crash recovery
- **WHEN** the plugin starts and finds a corrupted `data.json`
- **THEN** the system SHALL attempt to load a backup file
- **AND** if no backup exists, SHALL start with empty state and log a warning

### Requirement: Data schema versioning
The persisted data SHALL include a `schema_version` field. When the plugin loads data with an older schema version, it SHALL automatically migrate to the current version.

#### Scenario: Schema migration
- **WHEN** the plugin loads a `data.json` with `schema_version: 1` and the current version is 2
- **THEN** the system SHALL apply migration logic and update the schema_version

#### Scenario: Unknown schema version
- **WHEN** the plugin loads data with a schema version newer than the current plugin version
- **THEN** the system SHALL refuse to load, log an error, and start with empty state

