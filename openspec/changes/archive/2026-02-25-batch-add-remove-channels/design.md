## Context

LivePulse currently handles `/live add` and `/live remove` one channel at a time. The `cmd_add`/`cmd_remove` handlers receive at most 2 positional args from the AstrBot framework (`platform`, `channel_id`). Users managing multiple streamers must repeat the command for each channel.

Key current-state constraints:
- `Store.add_monitor()` / `remove_monitor()` are unlocked primitives — callers acquire `self.lock` externally.
- Single-channel add performs `check_status()` inside the lock, introducing network I/O under lock.
- `validate_channel()` is async and per-platform; Bilibili lacks `extract_id_from_url()` (URL parsing is inside `validate_channel`).
- i18n uses flat JSON with dot-notation keys across 3 locales.

## Goals / Non-Goals

**Goals:**
- Support batch add/remove of up to 20 channels in a single command.
- Unified response format for both N=1 and N>1 operations.
- Bounded concurrent validation (semaphore=5) with per-channel error isolation.
- Fine-grained error classification (not_found / rate_limited / invalid_format / internal_error).
- New `core/batch.py` module encapsulating all batch orchestration logic.
- New `Store.add_monitors_batch()` / `remove_monitors_batch()` methods with single-lock-acquisition semantics.

**Non-Goals:**
- Changing the AstrBot command framework signature (still 2 positional args).
- Adding a configurable batch size limit (hardcoded MAX_BATCH_SIZE=20).
- Immediate `check_status` after batch add (removed even for N=1; poller handles it).
- Refactoring platform checker error semantics beyond ensuring `RateLimitError` propagates.
- Rate-limit backoff within batch validation (semaphore is sufficient).

## Decisions

### D1: Batch args parsed from `event.message_str`

**Choice**: Parse raw message string in `cmd_add`/`cmd_remove`, split by whitespace after stripping the command prefix. The framework-provided `platform`/`channel_id` args are ignored for batch; `event.message_str` is the single source of truth.

**Why**: AstrBot only passes 2 positional args. Parsing `message_str` is the only way to get N args without framework changes. This is already the pattern used for URL auto-detect (single-arg mode).

**Alternative rejected**: Comma-separated single arg (`twitch a,b,c`) — less intuitive, breaks URL mode.

### D2: Mode detection — first arg determines mode

**Choice**: After splitting args from `message_str`:
1. If first arg matches a key in `PLATFORM_CHECKERS` (case-insensitive) → platform+ID mode.
2. Else if first arg contains `://` or matches `_HOST_PLATFORM_MAP` host patterns → URL mode.
3. Else → fall through to existing invalid-platform error.

Mixed-mode check: in platform+ID mode, if any subsequent arg looks like a URL → reject. In URL mode, if any arg matches a platform name without URL characteristics → reject.

**Why**: Simple, deterministic, no ambiguity. Matches user mental model.

### D3: New `core/batch.py` module

**Choice**: Create `core/batch.py` with two public async functions:
- `async def process_batch_add(store, origin, items, max_per_group, max_global, semaphore) -> BatchResult`
- `async def process_batch_remove(store, origin, items, semaphore) -> BatchResult`

Where `items` is a list of `BatchItem(platform: str, identifier: str, info: ChannelInfo | None)` prepared by the command handler after mode detection and preprocessing (dedup + truncation).

**Why over main.py helpers**: Batch logic is ~150 lines with its own data types. Separate module keeps `main.py` focused on command parsing and response formatting. Testable in isolation.

**Alternative rejected**: Extending `Store` with full batch orchestration — Store should remain a pure data layer.

### D4: Store batch methods — thin wrappers with single lock

**Choice**: Add to `Store`:
```python
async def add_monitors_batch(self, origin, items, max_per_group, max_global) -> list[str | None]:
    async with self.lock:
        results = [self.add_monitor(origin, p, info, max_per_group, max_global) for p, info in items]
        await self.persist()
        return results

async def remove_monitors_batch(self, origin, items) -> list[bool]:
    async with self.lock:
        results = [self.remove_monitor(origin, p, cid) for p, cid in items]
        await self.persist()
        return results
```

These are thin wrappers that call existing `add_monitor`/`remove_monitor` in a loop under one lock acquisition, then persist once.

**Why**: Minimal Store API change. `add_monitor` already does incremental limit checks (reads current count each call), so sequential calls under one lock naturally handle the "limit reached mid-batch" case.

**Alternative rejected**: Gemini's `batch_update(adds=[], removes=[])` — over-abstraction for current needs.

### D5: Concurrent validation with `asyncio.Semaphore(5)`

**Choice**: In `core/batch.py`, wrap each `validate_channel` call with a shared `asyncio.Semaphore(5)`. Use `asyncio.gather(*tasks, return_exceptions=True)` to collect results.

```python
async def _validate_one(sem, checker, identifier):
    async with sem:
        return await checker.validate_channel(identifier)
```

**Why**: Prevents flooding platform APIs. 5 is conservative enough for YouTube/Twitch/Bilibili rate limits while still providing meaningful speedup over sequential.

### D6: Error classification in batch processor

**Choice**: Classification happens in `core/batch.py` after `gather` returns:
- `ChannelInfo` result → `success`
- `None` result → `not_found`
- `RateLimitError` exception → `rate_limited`
- Other exception → `internal_error`

No new exception types needed. Twitch's `validate_channel` needs a minor fix: stop catching non-404 HTTP errors silently (let them propagate as `internal_error`).

**Why**: Classification at the batch layer avoids changing platform checker return types. Only Twitch needs a small fix (exception propagation).

### D7: Remove URL mode — allow network calls for Bilibili

**Choice**: Remove URL mode resolves URLs to `(platform, channel_id)` pairs. For most platforms, this is local extraction via `extract_id_from_url()`. For Bilibili (no `extract_id_from_url`), the system calls `validate_channel(url)` to resolve `room_id → uid`. This uses the same semaphore-bounded concurrency as add.

**Why**: Consistent UX — users can copy-paste the same URLs for add and remove. The network cost for Bilibili remove is acceptable (bounded by semaphore, max 20 channels).

### D8: Unified response format — single summary message

**Choice**: All batch operations (including N=1) produce:
```
[Summary line]: "Added: {success} succeeded, {fail} failed"
[Per-channel lines]:
  ✅ twitch | wpnebula (wpnebula)
  ❌ imcyv: channel not found
[Optional truncation line]: "⚠ 5 inputs skipped (max 20)"
```

New i18n keys under `cmd.batch.*` namespace. The command handler in `main.py` formats the response from `BatchResult`.

**Why**: Unified format simplifies code (one rendering path) and provides consistent UX. Breaking change to single-channel output format is acceptable per proposal.

### D9: No immediate `check_status` after add

**Choice**: Remove the `check_status` call from the add flow entirely (both batch and N=1). Newly added channels start with `initialized=False` and `last_status="unknown"`. The poller picks them up on its next cycle.

**Why**: `check_status` under lock blocks all other store operations. For batch, this would mean N sequential network calls under lock. Removing it for N=1 too keeps the code path unified and eliminates a long-standing lock-contention issue.

**Trade-off**: Users won't see immediate live/offline status after adding. The poller interval (default 60s) determines how quickly status appears.

## Risks / Trade-offs

**[Risk] Poller delay after add** → Users see "unknown" status for up to one polling interval. Mitigation: acceptable UX trade-off; poller interval is configurable. Future enhancement could notify poller to prioritize new channels.

**[Risk] Twitch exception propagation change** → Modifying Twitch's `validate_channel` error handling could surface previously-swallowed errors. Mitigation: only stop catching non-404 HTTP errors; 404 (channel not found) still returns `None`.

**[Risk] Bilibili remove URL mode network dependency** → Remove becomes non-instant for Bilibili URLs. Mitigation: bounded by semaphore(5) and MAX_BATCH_SIZE(20); platform+ID mode remains instant.

**[Risk] Breaking change to single-channel response format** → Existing users/bots parsing the old format will break. Mitigation: documented in proposal as accepted breaking change. Output format was never part of a stable API contract.

**[Risk] Lock contention during large batch** → 20 sequential `add_monitor` calls under lock blocks poller. Mitigation: `add_monitor` is pure in-memory (~microseconds per call); `persist()` is one disk write. Total lock hold time is negligible.

## Open Questions

None — all ambiguities resolved during the spec-plan phase.
