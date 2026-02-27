## ADDED Requirements

### Requirement: Atomic initialization flag
The system SHALL set `_initialized = True` only after ALL critical initialization steps complete successfully, ensuring the flag accurately reflects plugin readiness.

#### Scenario: Initialization succeeds fully
- **WHEN** all steps (persistence load, session creation, checker/notifier init, poller start) complete without exception
- **THEN** `_initialized` is set to `True`
- **THEN** plugin is ready to handle commands

#### Scenario: Exception occurs during initialization
- **WHEN** any step within `initialize()` raises an exception
- **THEN** `_initialized` remains `False`
- **THEN** all partially-created resources are cleaned up: poller tasks cancelled and awaited, `ClientSession` closed, `_pollers`/`_poller_tasks`/`_checkers` cleared, `_session` and `_notifier` reset to `None`
- **THEN** `initialize()` can be called again without resource leaks

#### Scenario: Retry after failed initialization
- **WHEN** `initialize()` previously failed and cleanup completed
- **THEN** a subsequent call to `initialize()` starts from a clean state
- **THEN** no duplicate pollers or tasks are created
