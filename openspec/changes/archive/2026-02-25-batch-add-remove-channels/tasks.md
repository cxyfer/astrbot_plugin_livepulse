## 1. Store Batch API

- [x] 1.1 Add `add_monitors_batch(origin, items: list[tuple[str, ChannelInfo]], max_per_group: int, max_global: int) -> list[str | None]` to `core/store.py`: acquire `self.lock` once, iterate calling `self.add_monitor()` per item, call `await self.persist()` once, release lock, return results list
- [x] 1.2 Add `remove_monitors_batch(origin, items: list[tuple[str, str]]) -> list[bool]` to `core/store.py`: same single-lock pattern, iterate calling `self.remove_monitor()` per item, persist once, return results list

## 2. Batch Processing Module

- [x] 2.1 Create `core/batch.py` with data types: `BatchItem(platform: str, identifier: str)`, `BatchResultItem(identifier: str, status: str, info: ChannelInfo | None, error_key: str | None)`, `BatchResult(items: list[BatchResultItem], truncated: int)`
- [x] 2.2 Implement `preprocess(raw_args: list[str], max_size: int = 20) -> tuple[list[str], int]`: silent dedup (preserve insertion order), truncation at MAX_BATCH_SIZE, return (unique_args, truncated_count)
- [x] 2.3 Implement `detect_mode(args: list[str], platform_checkers: dict) -> tuple[str, list[BatchItem]]`: first-arg mode detection (platform+ID vs URL), mixed-mode validation raising ValueError, return (mode, items)
- [x] 2.4 Implement `async process_batch_add(store, origin, items: list[BatchItem], checkers, max_per_group, max_global) -> BatchResult`: semaphore(5) bounded `asyncio.gather(return_exceptions=True)` for validation, error classification (ChannelInfo→success, None→not_found, RateLimitError→rate_limited, other→internal_error), then `store.add_monitors_batch()` for successful items, merge results
- [x] 2.5 Implement `async process_batch_remove(store, origin, items: list[BatchItem], checkers) -> BatchResult`: for platform+ID mode do local lookup (channel_id + display_id fallback), for URL mode do semaphore-bounded resolution via `validate_channel` or `extract_id_from_url`, then `store.remove_monitors_batch()`

## 3. Twitch Error Propagation Fix

- [x] 3.1 In `TwitchChecker.validate_channel()`, stop catching non-404 HTTP errors silently — let them propagate so the batch processor classifies them as `internal_error`. Keep 404 → return `None` behavior unchanged.

## 4. Command Handler Refactor

- [x] 4.1 Refactor `cmd_add` in `main.py`: parse batch args from `event.message_str` (split by whitespace after stripping command prefix), call `preprocess()`, call `detect_mode()`, delegate to `process_batch_add()`, format response from `BatchResult`. Remove the existing `check_status` call. Single-channel flows through the same batch path (N=1).
- [x] 4.2 Refactor `cmd_remove` in `main.py`: same pattern — parse from `event.message_str`, `preprocess()`, `detect_mode()`, delegate to `process_batch_remove()`, format response from `BatchResult`. Single-channel flows through batch path.
- [x] 4.3 Implement response formatter in `main.py`: takes `BatchResult` + operation type (add/remove), produces single aggregated message using `cmd.batch.*` i18n keys (summary line + per-channel result lines + optional truncation notice)

## 5. i18n Keys

- [x] 5.1 Add batch i18n keys to `en.json`: `cmd.batch.summary_add`, `cmd.batch.summary_remove`, `cmd.batch.item_success`, `cmd.batch.item_duplicate`, `cmd.batch.item_removed`, `cmd.batch.item_not_found`, `cmd.batch.item_fail`, `cmd.batch.item_limit_group`, `cmd.batch.item_limit_global`, `cmd.batch.truncated`, `cmd.batch.mixed_mode`
- [x] 5.2 Add same batch i18n keys to `zh-Hans.json` with Chinese Simplified translations
- [x] 5.3 Add same batch i18n keys to `zh-Hant.json` with Chinese Traditional translations
- [x] 5.4 Verify all 3 locale files have identical `{placeholder}` sets for every `cmd.batch.*` key

## 6. Testing

- [x] 6.1 Unit tests for `preprocess()`: dedup, truncation, dedup-before-truncation, empty input, single input
- [x] 6.2 Unit tests for `detect_mode()`: platform+ID detection, URL detection, mixed-mode rejection, single URL, single platform+ID, invalid platform
- [x] 6.3 Unit tests for `process_batch_add()`: all-success, partial-failure (not_found + rate_limited + internal_error), incremental limit check (group limit reached mid-batch), duplicate in store, semaphore concurrency bound (spy peak concurrency ≤ 5)
- [x] 6.4 Unit tests for `process_batch_remove()`: all-found, partial not-found, URL mode with bilibili network resolution, display_id fallback matching
- [x] 6.5 Unit tests for `Store.add_monitors_batch()` / `remove_monitors_batch()`: single lock acquisition (spy), single persist call (spy), incremental limit behavior, reverse_index consistency after batch
- [x] 6.6 Integration tests for `cmd_add` / `cmd_remove`: end-to-end batch add platform+ID, batch add URL, batch remove, N=1 unified format, mixed-mode rejection, truncation notice in response
- [x] 6.7 PBT: idempotency (batch_add twice → same state), commutativity (shuffled input → same state, given unique ≤ 20), round-trip (add then remove → original state), invariant preservation (monitor count ≤ limits), mode exclusivity (mixed input → zero mutations)
