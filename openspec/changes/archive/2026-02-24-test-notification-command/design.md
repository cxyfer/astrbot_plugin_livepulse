# Design: test-notification-command

## Decision: Bypass `_should_notify()` via `force` parameter

Add keyword-only `force: bool = False` to `Notifier.send_live_notification()` and `send_end_notification()`. When `force=True`, skip `_should_notify()` check entirely.

```python
async def send_live_notification(self, origin, platform, snapshot, global_enable, *, force=False):
    if not force and not self._should_notify(origin, global_enable, Transition.LIVE_START):
        return
    ...
```

Rationale: Minimal invasion, full code path reuse, no duplicate logic. Keyword-only prevents accidental positional misuse.

## Decision: Bypass failure tracking via `track_failure` parameter

Add keyword-only `track_failure: bool = True` to `_send_chain()`. When `False`, skip `increment_failure()` / `reset_failure()` calls. Test notifications pass `track_failure=False` through the `force` path.

Implementation: `send_*_notification` propagates a private `_track_failure` flag when `force=True`.

```python
async def _send_chain(self, origin, chain, *, track_failure=True):
    try:
        result = await self._ctx.send_message(origin, chain)
        if result is False:
            if track_failure:
                count = self._store.increment_failure(origin)
                logger.warning(...)
            return False
        if track_failure:
            self._store.reset_failure(origin)
        return True
    except Exception as e:
        if track_failure:
            count = self._store.increment_failure(origin)
            logger.warning(...)
        return False
```

## Decision: Async delay via `asyncio.create_task()`

Command handler yields confirmation immediately, then spawns a background task:

```python
@live.command("test_notify")
async def cmd_test_notify(self, event, delay: str):
    # validate, yield confirmation
    task = asyncio.create_task(self._run_test_notify(origin, delay_int))
    self._bg_tasks.add(task)
    task.add_done_callback(self._bg_tasks.discard)
```

Rationale: Consistent with poller pattern (`asyncio.create_task`). Using `set` + `add_done_callback` for automatic cleanup. `terminate()` cancels remaining tasks.

## Decision: Store `self._notifier` as instance attribute

Change `initialize()` to assign `self._notifier = notifier` so command handlers can access it. Add `self._notifier: Notifier | None = None` in `__init__`.

## Decision: Background task lifecycle management

Add `self._bg_tasks: set[asyncio.Task] = set()` in `__init__`. In `terminate()`, cancel all background tasks before closing session.

## Decision: Test data with thumbnail URL

Hardcoded `StatusSnapshot` with a static test image. Use `https://placehold.co/1280x720/orange/white?text=LivePulse+Test` as thumbnail — no external service dependency, deterministic rendering.

## Decision: Delay cap at 300 seconds

Maximum delay is 300 seconds. Values <= 0 or > 300 rejected with i18n error message.

## Decision: i18n keys under `cmd.test_notify.*`

New keys:
- `cmd.test_notify.scheduled` — confirmation with `{delay}` placeholder
- `cmd.test_notify.invalid_delay` — non-integer or <= 0
- `cmd.test_notify.delay_too_long` — exceeds 300s, with `{max}` placeholder
- `cmd.test_notify.not_ready` — plugin not initialized

Test notification content uses existing `notify.*` keys (same rendering path). The synthetic `StatusSnapshot` fields provide the "test" labeling (streamer_name = "Test Streamer", etc.).

## File Change Summary

| File | Change |
|------|--------|
| `core/notifier.py` | Add `force` param to `send_*`, `track_failure` param to `_send_chain`, propagate through `_deliver` |
| `main.py` | Add `self._notifier`, `self._bg_tasks`, `cmd_test_notify`, update `terminate()` |
| `i18n/en.json` | Add 4 keys |
| `i18n/zh-Hans.json` | Add 4 keys |
| `i18n/zh-Hant.json` | Add 4 keys |
