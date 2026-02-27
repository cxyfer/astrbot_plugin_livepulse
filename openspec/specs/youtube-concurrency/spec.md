## ADDED Requirements

### Requirement: YouTube concurrent channel status check
The system SHALL replace the serial for-loop in `check_status()` with `asyncio.gather` limited by `asyncio.Semaphore(10)` to reduce wall-clock polling time to O(ceil(N/10) × latency).

#### Scenario: Concurrent execution with semaphore
- **WHEN** `check_status()` is called with N channel IDs
- **THEN** all N tasks are scheduled via `asyncio.gather`
- **THEN** at most 10 `_check_single` calls execute concurrently at any moment (enforced by `asyncio.Semaphore(10)`)

#### Scenario: Non-RateLimitError exception in one channel
- **WHEN** `_check_single(cid, session)` raises an exception that is not `RateLimitError`
- **THEN** the worker wraps it as `StatusSnapshot(success=False, ...)`
- **THEN** other channels continue executing
- **THEN** the final result dict contains `cid` mapped to a failed snapshot

#### Scenario: RateLimitError from any channel
- **WHEN** `_check_single(cid, session)` raises `RateLimitError`
- **THEN** `asyncio.gather` propagates it (since `return_exceptions=False`)
- **THEN** `check_status()` raises `RateLimitError` to the caller
- **THEN** it is NOT converted to a failed `StatusSnapshot`

#### Scenario: Result determinism
- **WHEN** no `_check_single` raises `RateLimitError`
- **THEN** returned mapping contains exactly one entry per input channel ID
- **THEN** result is equivalent to serial execution for the same deterministic stubs
