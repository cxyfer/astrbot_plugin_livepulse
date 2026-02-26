# Tasks: Fix Live Notification Username Format

## PBT Properties (Property-Based Testing)

| Invariant | Falsification Strategy |
|-----------|----------------------|
| Bilibili format always contains `@` and `()` | Input without UID or empty username |
| Twitch same name does NOT contain `(@)` | Input display_name and login_name differ only by case |
| Formatted result is NEVER empty | Input empty string or None |
| Backward compatible: old data without `login_name` still displays | Input snapshot missing `login_name` field |

---

## Task 1: Update Data Model

**File**: `core/models.py`

- [x] Add `login_name: str | None = None` field to `StatusSnapshot` dataclass

**Verification**: `grep "login_name" core/models.py` should show the new field

**Risk**: None (optional field, backward compatible)

---

## Task 2: Update Bilibili Adapter

**File**: `platforms/bilibili.py`

- [x] In `check_status()`, set `display_id=uid` when creating `StatusSnapshot`

**Code Location**: Lines 58-66

**Verification**: Bilibili `StatusSnapshot` should include `display_id=uid`

**Risk**: Low - display_id was already optional, now being populated

---

## Task 3: Update Twitch Adapter

**File**: `platforms/twitch.py`

- [x] In `check_status()`, extract `user_login` from stream data
- [x] Set `display_id=user_login` when creating `StatusSnapshot`
- [x] Set `login_name=user_login` when creating `StatusSnapshot`

**Code Location**: Lines 86-94

**Verification**: Twitch `StatusSnapshot` should include both `display_id` and `login_name`

**Risk**: Medium - Twitch offline status loses display_name, end notification may show login only

**Mitigation**: Use `MonitorEntry.channel_name` as fallback for end notifications

---

## Task 4: Update Notifier

**File**: `core/notifier.py`

- [x] Add `_format_streamer_name()` method with platform-specific logic
- [x] Update `_build_live_embed()` to use formatted name
- [x] Update `_build_end_embed()` to use formatted name (if applicable)

**Code Locations**:
- New method after line 145
- Modify `_build_live_embed()` (lines 154-177)
- Modify `_build_end_embed()` (lines 179-195)

**Critical**: Bypass i18n `notify.embed.footer` template to avoid duplicate formatting

**Verification**:
- Bilibili: `@嘉然今天吃什么 (672328094)`
- Twitch same name: `ScottyBVB`
- Twitch different name: `日本語配信者 (@japanese_streamer)`

**Risk**: High - i18n footer template conflict

**Mitigation**: Use pre-formatted name directly as footer, skip template

---

## Task 5: Add Unit Tests

**File**: `tests/test_notifier.py` (create if not exists)

- [x] Test `_format_streamer_name()` for Bilibili format
- [x] Test `_format_streamer_name()` for Twitch same name
- [x] Test `_format_streamer_name()` for Twitch different name
- [x] Test `_format_streamer_name()` for default/unknown platform
- [x] Test `_format_streamer_name()` with empty/None inputs (edge cases)
- [x] Test `_format_streamer_name()` with display_id containing `@` (normalization)

**Verification**: All new tests pass with `pytest tests/test_notifier.py -v`

---

## Task 6: Update Existing Tests

**Files**: `tests/*.py`

- [x] Update any tests that assert on `StatusSnapshot` fields
- [x] Update any tests that check notification message format

**Verification**: All existing tests pass with `pytest -v`

---

## Task 7: Regression Testing

- [x] Run full test suite: `pytest -v`
- [x] Verify no breaking changes in existing functionality

**Acceptance Criteria**: 100% of existing tests pass

---

## Implementation Order

1. Task 1 (Data Model) - Required by Tasks 2, 3, 4
2. Task 2 (Bilibili) - Independent
3. Task 3 (Twitch) - Independent
4. Task 4 (Notifier) - Depends on Tasks 1, 2, 3
5. Task 5 (Unit Tests) - Depends on Task 4
6. Task 6 (Update Tests) - Depends on Tasks 1-4
7. Task 7 (Regression) - Depends on all above

---

## Multi-Model Analysis Summary

### Codex Key Findings
- **High Risk**: Twitch end notification loses display_name when stream goes offline
- **High Risk**: i18n footer template conflicts with new formatting
- **Recommendation**: Centralize formatting in Notifier, not in platform checkers

### Gemini Key Findings
- **Maintainability Score**: Medium - current formatting is fragmented
- **Integration Conflict**: i18n footer template will produce messy results
- **Recommendation**: Introduce centralized formatting utility in Notifier
