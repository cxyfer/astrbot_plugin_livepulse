# Tasks: test-notification-command

## Task 1: Add `force` and `track_failure` parameters to Notifier

**File**: `core/notifier.py`

- [x] Add `*, force: bool = False` keyword-only param to `send_live_notification()`
- [x] Add `*, force: bool = False` keyword-only param to `send_end_notification()`
- [x] In both methods: when `force` is `True`, skip `_should_notify()` call
- [x] Add `*, track_failure: bool = True` keyword-only param to `_send_chain()`
- [x] In `_send_chain()`: guard `increment_failure()` and `reset_failure()` behind `if track_failure`
- [x] Add `*, track_failure: bool = True` keyword-only param to `_deliver()`
- [x] In `_deliver()`: pass `track_failure` through to `_send_chain()` calls
- [x] In `send_live_notification()`: when `force=True`, pass `track_failure=False` to `_send_chain()` and `_deliver()`
- [x] In `send_end_notification()`: when `force=True`, pass `track_failure=False` to `_send_chain()` and `_deliver()`

## Task 2: Store `self._notifier` and add background task management in main.py

**File**: `main.py`

- [x] Add `self._notifier: Notifier | None = None` in `__init__()`
- [x] Add `self._bg_tasks: set[asyncio.Task] = set()` in `__init__()`
- [x] In `initialize()`: assign `self._notifier = notifier` after creating Notifier instance
- [x] In `terminate()`: cancel all tasks in `self._bg_tasks` and await them (before closing session)

## Task 3: Implement `cmd_test_notify` command

**File**: `main.py`

- [x] Add `@live.command("test_notify")` handler method `cmd_test_notify(self, event: AstrMessageEvent, delay: str | None = None)`
- [x] Validate `self._notifier is not None` → yield `cmd.test_notify.not_ready` if None
- [x] Handle missing delay (None) → yield `cmd.test_notify.invalid_delay`
- [x] Parse `delay` to int via try/except ValueError → yield `cmd.test_notify.invalid_delay` on failure
- [x] Validate `delay > 0` → yield `cmd.test_notify.invalid_delay` if not
- [x] Validate `delay <= 300` → yield `cmd.test_notify.delay_too_long` with `max=300` if exceeded
- [x] Per-origin rate limit: reject if a test_notify task is already pending for the same origin
- [x] Create task before yielding confirmation (avoid async generator lifecycle risk)
- [x] Create `_run_test_notify(self, origin: str, delay: int)` async method:
  - `await asyncio.sleep(delay)`
  - Build synthetic `StatusSnapshot(is_live=True, streamer_name="Test Streamer", title="Test Stream Title", category="Just Chatting", stream_url="https://example.com/test", thumbnail_url="https://placehold.co/1280x720/orange/white?text=LivePulse+Test")`
  - Call `self._notifier.send_live_notification(origin, "test", snapshot, global_enable=True, force=True)`
  - Call `self._notifier.send_end_notification(origin, "test", "Test Streamer", global_enable=True, global_end_enable=True, force=True)`
- [x] Spawn task via `asyncio.create_task(self._run_test_notify(...), name=f"test_notify:{origin}")`
- [x] Add task to `self._bg_tasks` with `task.add_done_callback(self._bg_tasks.discard)`

## Task 4: Add i18n keys

**Files**: `i18n/en.json`, `i18n/zh-Hans.json`, `i18n/zh-Hant.json`

- [x] `en.json`: Add 5 keys (scheduled, invalid_delay, delay_too_long, not_ready, already_pending)
- [x] `zh-Hans.json`: Add 5 keys
- [x] `zh-Hant.json`: Add 5 keys
