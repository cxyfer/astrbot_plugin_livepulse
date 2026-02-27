# Design: livepulse-plugin-review-fixes

## Context

Five isolated bug fixes identified by the AstrBot plugin review bot (Issue #5489). Each fix targets a specific file with no cross-cutting architectural changes. All fixes are backward-compatible.

## Goals / Non-Goals

**Goals**: Fix the 5 review issues with minimal, surgical changes.

**Non-Goals**: Refactor overall architecture, add metrics/monitoring, address Twitch/YouTube `_resolve_*` 429 handling, or migrate storage conventions.

## Decisions

### R1: Use `_parse_batch_args()` for notify arg extraction

**Decision**: Replace `parts = event.message_str.strip().split(); arg = parts[1]` with `raw_args = self._parse_batch_args(event, "notify"); arg = raw_args[0] if raw_args else None` in both `cmd_notify` and `cmd_end_notify`.

**Why**: `_parse_batch_args()` already strips the command prefix and returns the remaining tokens. Using `parts[1]` on `"live notify on"` yields `"notify"`, not `"on"`. The helper is already used in `cmd_add`/`cmd_remove` for the same purpose.

**Alternative rejected**: `parts[-1]` — cannot reject malformed inputs like `"live notify foo on"`.

---

### R2: Move `_initialized = True` to end of try block; cleanup in except

**Decision**:
1. Remove `self._initialized = True` from its current early position.
2. Place it immediately after all critical steps (session, checkers, notifiers, pollers) succeed.
3. In the `except` block: cancel + gather `_poller_tasks`, close `_session`, clear `_pollers`/`_poller_tasks`/`_checkers`, set `_session = None`, `_notifier = None`, re-raise.

**Why**: Marking initialized before async operations makes the flag unreliable. Failure mid-init leaves the plugin in an unrecoverable state requiring bot restart.

**Risk → Mitigation**: Exceptions during task cancellation must be swallowed (`asyncio.CancelledError` expected). Do NOT call `terminate()` from the except block — it sets `_terminated = True` permanently.

---

### R3: Exponential backoff written in `_process_results()`

**Decision**: On `success=False`: `failures = self._channel_failures.get(cid, 0) + 1; self._channel_failures[cid] = failures; delay = min(_BACKOFF_BASE * (_BACKOFF_MULT ** (failures - 1)), _BACKOFF_MAX); self._channel_backoff_until[cid] = time.time() + delay`. On `success=True`: pop both dicts.

**Parameters** (use existing constants, verify they exist or add):
- `_BACKOFF_BASE`: base delay in seconds (e.g., 30)
- `_BACKOFF_MULT`: exponential multiplier (e.g., 2)
- `_BACKOFF_MAX`: cap at 300 seconds

**Why**: The dicts are declared and the backoff filter is used in `_poll_loop`, but writes never happen — backoff is effectively disabled.

**Risk → Mitigation**: `time.time()` skew across channels is acceptable (sub-millisecond). No jitter added to keep behavior deterministic and testable.

---

### R4: HTTP 429 check before `raise_for_status()` in Bilibili

**Decision**: In both `_resolve_room_id()` and `_validate_uid()`:
1. Insert `if resp.status == 429: raise RateLimitError("bilibili")` before `resp.raise_for_status()`.
2. Add `except RateLimitError: raise` immediately before the existing `except Exception as e:` handler.

**Why**: `raise_for_status()` raises `aiohttp.ClientResponseError`, not `RateLimitError`. The generic `except Exception` catches everything including the new `RateLimitError` if step 2 is omitted — that's the critical ordering requirement.

**Scope limited to**: `bilibili.py` only. Twitch/YouTube `_resolve_*` methods are out of scope per proposal.

---

### R5: `asyncio.Semaphore(10)` + `asyncio.gather` in YouTube `check_status()`

**Decision**:
```python
async def check_status(self, channel_ids, session):
    sem = asyncio.Semaphore(10)
    async def _run_one(cid):
        async with sem:
            try:
                return cid, await self._check_single(cid, session)
            except RateLimitError:
                raise
            except Exception as e:
                logger.warning(...)
                return cid, StatusSnapshot(success=False, ...)
    pairs = await asyncio.gather(*(_run_one(cid) for cid in channel_ids))
    return dict(pairs)
```

**Why**: Serial loop adds latency linearly with channel count. Semaphore prevents connection pool exhaustion. `return_exceptions=False` lets `RateLimitError` propagate naturally.

**Risk → Mitigation**: `asyncio.gather` cancels remaining tasks on exception — aiohttp handles `CancelledError` gracefully on the session. Concurrent log ordering may differ from serial, which is acceptable.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| R2: cleanup may swallow init errors | Re-raise original exception after cleanup |
| R3: large failure counts before first success | Exponent capped by `_BACKOFF_MAX`; no unbounded growth |
| R5: RateLimitError cancels all in-flight tasks | aiohttp `ClientSession` handles cancellation; tasks are lightweight |

## Open Questions

None — all ambiguities resolved by proposal constraints and dual-model analysis.
