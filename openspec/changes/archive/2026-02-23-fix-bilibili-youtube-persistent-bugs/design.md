# Design: Fix Bilibili/YouTube Persistent Bugs

## Context

Previous fix (953dfee) rewrote channel validation and live detection but both platforms remain non-functional in production:

- **Bilibili**: All HTTP calls fail with 412 (Precondition Failed) because the shared `aiohttp.ClientSession` sends a bare `aiohttp/{version}` User-Agent.
- **YouTube**: `_is_blocked()` false-positives on every page because it matches `"captcha"` — a string present in all normal YouTube pages via `RECAPTCHA_V3_SITEKEY` and `.grecaptcha-badge`.
- **cmd_add**: Broad `except Exception` masks `RateLimitError` as "channel not found".

Current architecture: all platform checkers share a single `aiohttp.ClientSession` created in `main.py:59` with no default headers. YouTube adds per-request headers; Bilibili and Twitch do not.

## Goals / Non-Goals

**Goals:**
- Bilibili `check_status`, `_resolve_room_id`, `_validate_uid` return valid data (no 412)
- YouTube `_is_blocked()` returns `False` on normal pages, `True` only on genuine block pages
- `cmd_add` surfaces `RateLimitError` as a distinct user-facing message

**Non-Goals:**
- Migrating YouTube to official Data API (requires API key/quota)
- Per-platform session isolation (overkill for current plugin size)
- Adding retry/backoff logic to Bilibili (existing poller retry is sufficient)
- Fixing `_get_channel_name()` to call `_is_blocked()` (low traffic path, no reported issues)

## Decisions

### D1: Shared UA constant in `platforms/__init__.py`

Define `DEFAULT_USER_AGENT` in `platforms/__init__.py`. Both `main.py` (session init) and `youtube.py` (per-request headers) import from this single source of truth.

**Rationale**: Eliminates divergent UA literals. A single constant means future UA updates propagate everywhere automatically.

**Alternatives considered**:
- *Inline in main.py*: YouTube would still have its own copy — drift risk.
- *Per-request headers in bilibili.py*: Duplicated across 3 call sites, easy to miss on new endpoints.

### D2: Session-level default headers (User-Agent only)

Initialize session as `aiohttp.ClientSession(headers={"User-Agent": DEFAULT_USER_AGENT})`.

Only `User-Agent` is set globally — no `Accept-Language`, `Referer`, or other headers at session level.

**Rationale**: Minimal blast radius. YouTube already sets `Accept-Language` per-request. Twitch uses `Client-ID`/`Authorization` per-request which merge cleanly with session-level UA (aiohttp merges per-request headers on top of session defaults).

**Impact on Twitch**: Verified — `TwitchChecker._headers()` returns `Client-ID` and `Authorization`. These merge with session UA. Twitch API and OAuth endpoints accept arbitrary UA values. No conflict.

### D3: `_is_blocked()` — single-signal detection

Replace current logic:
```python
# BEFORE (always true on normal pages)
def _is_blocked(html: str) -> bool:
    return "captcha" in html.lower() or "unusual traffic" in html.lower()

# AFTER
def _is_blocked(html: str) -> bool:
    return "unusual traffic" in html.lower()
```

**Rationale**: "unusual traffic from your computer network" is YouTube's canonical block indicator. Normal pages never contain this phrase. The `"captcha"` substring appears in every YouTube page (reCAPTCHA v3 sitekey, grecaptcha-badge CSS) and must be removed entirely.

HTTP 429 is already handled at the caller level (`_check_single` line 45-46) and does not flow through `_is_blocked()`.

**Alternatives considered**:
- *Multi-signal (unusual traffic + no ytInitialData)*: More robust against edge cases but also more brittle — truncated responses could false-positive on missing `ytInitialData`. Per proposal preference: "better to miss a rare block than to false-positive on every request".
- *No HTML detection at all (429 only)*: Would miss block pages served as HTTP 200.

### D4: `cmd_add` exception taxonomy

Add `RateLimitError` catch before generic `Exception` in `cmd_add`:

```python
try:
    info = await checker.validate_channel(channel_id, self._session)
except RateLimitError as e:
    yield event.plain_result(self._t(event, "error.rate_limited", platform=e.platform))
    return
except Exception as e:
    # existing invalid_channel path unchanged
```

**Rationale**: `RateLimitError` has a `.platform` attribute — use it directly as the i18n placeholder source. Generic `Exception` catch preserved for true validation failures (network, parse errors).

### D5: New i18n key `error.rate_limited`

Add to all 3 locale files with `{platform}` placeholder:
- **en**: `"{platform} is currently rate-limiting requests. Please try again later."`
- **zh-Hans**: `"{platform} 目前正在限制请求频率，请稍后再试。"`
- **zh-Hant**: `"{platform} 目前正在限制請求頻率，請稍後再試。"`

## Risks / Trade-offs

| Risk | Level | Mitigation |
|------|-------|------------|
| Bilibili tightens anti-bot beyond UA (Referer, cookie, challenge) | Medium | Session-level UA is the minimal fix; if 412 returns, add Bilibili-specific headers as targeted follow-up |
| YouTube changes block page text (no "unusual traffic" phrase) | Medium | False negative = treated as offline instead of rate-limited. Acceptable per proposal: "better to miss a rare block than to false-positive" |
| Truncated HTML response missing block signals | Low | Truncated page with no `unusual traffic` → treated as normal → parser finds no live marker → offline. Safe degradation. |
| Session-level UA string ages out | Low | Static Chrome UA; can be updated in single constant if needed |
| `cmd_check` handle resolution (main.py:222-225) still catches broad Exception | Low | Out of scope for this change; `cmd_check` already uses `error.generic` for exceptions which includes the error string |

## PBT Properties

### P1: UA Invariant
**Invariant**: All Bilibili requests sent via the shared session include `User-Agent == DEFAULT_USER_AGENT`.
**Falsification**: Intercept outgoing headers on randomized request sequences; fail if any request lacks UA or has wrong value.

### P2: Block Detection Purity
**Invariant**: `_is_blocked(html)` is equivalent to `"unusual traffic" in html.lower()` for all inputs.
**Falsification**: Generate random HTML strings with/without the phrase; compare function output against oracle. Inject `"captcha"` variants — must not affect result.

### P3: Exception Routing
**Invariant**: `RateLimitError` in `cmd_add` always yields `error.rate_limited`, never falls through to generic `Exception` handler.
**Falsification**: Stub `validate_channel` to raise `RateLimitError(platform=p)`; verify output i18n key and `{platform}` value equals `p`.

### P4: Fallback Preservation
**Invariant**: Non-`RateLimitError` exceptions in `cmd_add` still yield `cmd.add.invalid_channel`.
**Falsification**: Raise `ValueError`, `RuntimeError`, custom exceptions; verify none trigger `error.rate_limited`.
