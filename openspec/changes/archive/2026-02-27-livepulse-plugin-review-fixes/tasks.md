## 1. R1 — Fix notify command argument parsing (main.py)

- [x] 1.1 In `cmd_notify`: replace `parts = event.message_str.strip().split()` + `arg = parts[1] if len(parts) > 1 else None` with `raw_args = self._parse_batch_args(event, "notify")` + `arg = raw_args[0] if raw_args else None`
- [x] 1.2 In `cmd_end_notify`: apply same replacement using `_parse_batch_args(event, "end_notify")`
- [x] 1.3 Remove now-unused `parts` variable assignments from both methods
- [x] 1.4 Write unit tests: `"live notify on"` → `arg="on"`, `"live notify off"` → `arg="off"`, `"live notify"` → `arg=None`, `"live notify foo"` → invalid branch

## 2. R2 — Fix initialization state flag timing (main.py)

- [x] 2.1 Remove `self._initialized = True` from its current early position in `initialize()`
- [x] 2.2 Wrap the critical init body (session creation through poller startup) in `try/except Exception`
- [x] 2.3 Place `self._initialized = True` immediately after all steps succeed (before/at the success log line)
- [x] 2.4 In `except` block: cancel each task in `self._poller_tasks` and gather them; close `self._session` if not None; clear `self._pollers`, `self._poller_tasks`, `self._checkers`; set `self._session = None`, `self._notifier = None`; re-raise
- [x] 2.5 Write unit tests: mock one init step to raise → verify `_initialized=False`, no leaked tasks/session; then call `initialize()` again → succeeds with exactly one set of pollers

## 3. R3 — Implement channel-level backoff writes (core/poller.py)

- [x] 3.1 Verify `_BACKOFF_BASE`, `_BACKOFF_MULT`, `_BACKOFF_MAX` constants exist; add if missing (BASE=30, MULT=2, MAX=300)
- [x] 3.2 In `_process_results()`, failure branch: increment `_channel_failures[cid]`, compute `delay = min(_BACKOFF_BASE * (_BACKOFF_MULT ** (failures - 1)), _BACKOFF_MAX)`, write `_channel_backoff_until[cid] = time.time() + delay`
- [x] 3.3 Verify success branch already clears both dicts via `pop`; add if missing
- [x] 3.4 Write unit tests: 1 failure → backoff set; n failures → delay non-decreasing and ≤ 300s; success → both dicts cleared; cross-channel independence

## 4. R4 — Propagate Bilibili HTTP 429 as RateLimitError (platforms/bilibili.py)

- [x] 4.1 In `_resolve_room_id()`: add `if resp.status == 429: raise RateLimitError("bilibili")` before `resp.raise_for_status()`
- [x] 4.2 In `_resolve_room_id()`: add `except RateLimitError: raise` before the existing `except Exception as e:` handler
- [x] 4.3 In `_validate_uid()`: add `if resp.status == 429: raise RateLimitError("bilibili")` before `resp.raise_for_status()`
- [x] 4.4 In `_validate_uid()`: add `except RateLimitError: raise` before the existing `except Exception as e:` handler
- [x] 4.5 Write unit tests: mock 429 → `RateLimitError` raised; mock non-429 HTTP error → `None` returned; mock 200 → valid value returned

## 5. R5 — YouTube concurrent polling with Semaphore (platforms/youtube.py)

- [x] 5.1 Add `import asyncio` if not already imported in `youtube.py`
- [x] 5.2 Replace the serial `for cid in channel_ids` loop in `check_status()` with a semaphore-guarded worker function
- [x] 5.3 Define `sem = asyncio.Semaphore(10)` at start of `check_status()`
- [x] 5.4 Define inner `async def _run_one(cid)`: `async with sem:` → call `await self._check_single(cid, session)` → `except RateLimitError: raise` → `except Exception: return (cid, StatusSnapshot(success=False, ...))`
- [x] 5.5 Replace loop with `pairs = await asyncio.gather(*(_run_one(cid) for cid in channel_ids))` and `return dict(pairs)`
- [x] 5.6 Write unit tests: deterministic stubs → result equals serial execution; semaphore limit → max 10 concurrent; `RateLimitError` in one channel → propagates from `check_status()`; non-RateLimit exception → failed snapshot in result
