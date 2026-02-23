# Fix Bilibili/YouTube Persistent Bugs

## Context

The previous fix (953dfee) rewrote channel validation and live detection logic but both platforms remain non-functional in production. User reports show:

- **Bilibili**: All `validate_channel` and `check_status` calls fail silently — every `/live add bilibili <id>` returns "找不到頻道"
- **YouTube**: Every page fetch triggers `RateLimitError` — `/live check youtube` returns "Rate limited by youtube", `/live list` shows perpetual `[unknown]` status

## Root Cause Analysis

### BUG-1: Bilibili HTTP 412 — Missing User-Agent

**Evidence**: Bilibili API (`api.live.bilibili.com`) now returns HTTP 412 (Precondition Failed) for requests with Python-like User-Agent strings (`aiohttp/x.y.z`, `Python-urllib/3.x`).

- `bilibili.py` makes all HTTP calls via bare `session.post()`/`session.get()` with no custom headers
- `aiohttp.ClientSession()` in `main.py:59` is created without default headers → sends `aiohttp/{version}` as User-Agent
- All 3 code paths affected: `check_status` (POST), `_resolve_room_id` (GET), `_validate_uid` (POST)

**Verification**: Same POST to `get_status_info_by_uids` succeeds with browser UA, fails with `Python/aiohttp` UA.

### BUG-2: YouTube False-Positive Rate Limiting — Broken `_is_blocked()`

**Evidence**: `_is_blocked()` at `youtube.py:165-166` checks `"captcha" in html.lower()`. Every normal YouTube page contains:
1. `RECAPTCHA_V3_SITEKEY` in embedded JSON config
2. `.grecaptcha-badge{visibility:hidden}` in CSS

These are standard YouTube page elements, **not** indicators of an actual block. Result: `_is_blocked()` **always returns True** → every YouTube request raises `RateLimitError`.

**Affected flows**:
- `_check_single()` → `_is_blocked` → `RateLimitError` → poller enters backoff → status never updates → `[unknown]` forever
- `_resolve_handle()` → `_is_blocked` → `RateLimitError` → caught by `cmd_add` as generic Exception → "找不到頻道"
- `cmd_check` catches `RateLimitError` → "Rate limited by youtube"

## Requirements

### R1: Bilibili requests must include browser-like User-Agent

- **Constraint**: All HTTP calls in `BilibiliChecker` must send a `User-Agent` header that Bilibili's 412 filter accepts
- **Scope**: `check_status`, `_resolve_room_id`, `_validate_uid`
- **Implementation approach**: Set default headers on the shared `aiohttp.ClientSession` in `main.py`, OR add per-request headers in `BilibiliChecker` (like YouTube already does)
- **Preferred**: Set session-level default headers — single change point, benefits all platforms

### R2: YouTube `_is_blocked()` must not false-positive on normal pages

- **Constraint**: Must distinguish real block pages from normal pages containing standard `recaptcha`/`grecaptcha` strings
- **Distinguishing signals for real blocks**:
  - Page has NO `ytInitialData` (normal pages always have it, ~900KB+)
  - Page title contains "Before you continue" or "Are you a robot"
  - Page contains `<form` with action containing "consent"
  - Literal phrase "unusual traffic from your computer network"
- **Minimum viable fix**: Check for `"unusual traffic"` only, or verify absence of `ytInitialData`

### R3: RateLimitError must surface correctly in cmd_add

- **Current**: `cmd_add` line 151 catches `Exception` broadly → shows "找不到頻道" even for rate limit errors
- **Constraint**: `RateLimitError` should propagate as a distinct error message, not be masked as "channel not found"

## Success Criteria

| ID | Scenario | Expected |
|----|----------|----------|
| SC-1 | `POST get_status_info_by_uids` with `uids=[2978046]` | HTTP 200, returns user data |
| SC-2 | `GET get_info?room_id=60989` | HTTP 200, resolves to uid 2978046 |
| SC-3 | `/live add bilibili 2978046` | Success message with "翼侯大人" |
| SC-4 | `/live add bilibili https://live.bilibili.com/60989` | Success message with "翼侯大人" |
| SC-5 | `_is_blocked(normal_youtube_html)` returns `False` | No false-positive RateLimitError |
| SC-6 | `/live check youtube @HakosBaelz` | Returns live/offline status (not rate limit error) |
| SC-7 | `/live list` after successful polling | Shows `[live]` or `[offline]`, not `[unknown]` |
| SC-8 | `/live add youtube @Handle` when YouTube is actually blocked | Shows rate limit error, not "找不到頻道" |

## Constraints

- **Hard**: No new dependencies — fix must use existing `aiohttp` session mechanics
- **Hard**: Changes must not break Twitch checker (which doesn't use the shared session for HTML scraping)
- **Soft**: Prefer session-level default headers over per-request headers for maintainability
- **Soft**: `_is_blocked` should remain conservative — better to miss a rare block than to false-positive on every request
