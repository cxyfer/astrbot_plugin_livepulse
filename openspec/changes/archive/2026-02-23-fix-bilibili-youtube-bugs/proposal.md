# Fix Bilibili & YouTube Platform Bugs

## Context

Three confirmed bugs in the LivePulse plugin affecting Bilibili and YouTube platform integrations:

1. **Bilibili**: Cannot add channels — neither username nor UID works
2. **YouTube**: Channel names display as `[unknown]` after adding
3. **YouTube**: Live status detection returns incorrect results

## Root Cause Analysis

### Bug 1: Bilibili `validate_channel` Only Accepts Pure Numeric UID

**File**: `platforms/bilibili.py:65-69`

```python
async def validate_channel(self, channel_id: str, session: ClientSession) -> ChannelInfo | None:
    try:
        int(channel_id)
    except ValueError:
        return None  # <-- Rejects ALL non-numeric input (usernames)
```

The `validate_channel` method immediately returns `None` for any non-numeric input. There is **no username-to-UID resolution** implemented. Users typing usernames like `翼侯大人` or `@翼侯大人` get "channel not found".

For numeric UID input (e.g., `2978046`), the API call itself works correctly (verified via curl: `get_status_info_by_uids` returns `code: 0` with valid data). However, the actual issue depends on whether the API returns the UID key in the response. Testing confirmed the API **does** return data correctly for UID `2978046`, so the numeric path should work.

**CRITICAL**: Retesting revealed the numeric UID path works at the API level. The bug for numeric UIDs may be in how the Bilibili API response is structured — the key in `data` might be an integer string that doesn't match. Further investigation needed, but the username path is definitively broken.

**UPDATE after re-analysis**: The API returns `data.{uid_string}` correctly. The `validate_channel` method calls the API correctly and parses the response. The numeric UID path (`2978046`) SHOULD work. If it doesn't in production, possible causes:
- Network issues in the deployment environment
- The `int(channel_id)` check passes but the POST request fails silently
- Cookie/rate-limit issues specific to the server's IP

**The username resolution is definitively missing** — this is the primary Bilibili bug.

### Bug 2: YouTube Channel Name Shows `[unknown]`

**File**: `platforms/youtube.py:87-106` (`_resolve_handle`) and `platforms/youtube.py:104`

**CRITICAL DISCOVERY**: `_CHANNEL_ID_RE` (`r'"channelId"\s*:\s*"(UC[\w-]{22})"'`) grabs the **first** `"channelId"` on the page, which is often from recommended/related content rather than the page owner. Verified wrong for both test channels:
- `@HakosBaelz`: regex returned `UC8rcEBzJSleTkf_-agPM20g`, correct is `UCgmPnx-EEeOrZSg5Tiw7ZRQ`
- `@EarendelXDFP`: regex returned `UCFiIsVOC1p_gfTYDYXXfl4g`, correct is `UCwzpXmWAFEVKH3VzwvSlY_w`

The `_resolve_handle` method fetches `https://www.youtube.com/@handle` and searches for `"author"` in the HTML:

```python
name_match = re.search(r'"author"\s*:\s*"([^"]+)"', html)
name = name_match.group(1) if name_match else handle
```

**Verified via curl**: The YouTube handle page (`/@HakosBaelz`, `/@EarendelXDFP`) **does NOT contain** the `"author"` field in its HTML. The `"author"` field only exists on video/live pages, not channel pages.

However, the fallback is `handle` (the `@` handle string), not `[unknown]`. The `[unknown]` comes from `MonitorEntry.last_status` being `"unknown"` (initial state), which gets displayed in the list command as the status tag `[unknown]`, not the channel name. Looking at `main.py:203`:

```python
status = entry.last_status if entry.initialized else "unknown"
lines.append(self._t(event, "cmd.list.entry", status=status, platform=platform, name=entry.channel_name, channel_id=cid))
```

The `[unknown]` is the **status** (not yet polled), not the channel name. The channel name fallback to `handle` works but the `"author"` regex failure means we get the `@handle` string instead of the display name.

**Real issue**: The `_resolve_handle` should extract the channel display name from a different field. The handle page contains `"name"` or channel title in `og:title` meta tag or `"title"` in `ytInitialData`.

### Bug 3: YouTube Live Status Detection Incorrect

**File**: `platforms/youtube.py:38-51` (`_check_single`)

The method fetches `https://www.youtube.com/channel/{channel_id}/live` and checks:

```python
is_live = '"isLive":true' in html or "hqdefault_live.jpg" in html
```

**Verified via curl**: The `/live` page **does** return `"isLive":true` for the channel. However, the critical discovery is that **YouTube redirects the `/live` URL to a different channel's stream**. For `@HakosBaelz`, the `/live` page redirected to IRyS's stream, returning `"author":"IRyS Ch. hololive-EN"`.

This means:
- When the channel IS live, the page shows their own stream → `isLive:true` ✓
- When the channel is NOT live but YouTube recommends another live stream, it MAY redirect → `isLive:true` from another channel (false positive)
- When no redirect happens, the page shows no live content → `isLive:false`

The `/live` endpoint behavior is unreliable because YouTube may redirect to recommended content. The `check_status` in the poller uses the **resolved channel_id** (e.g., `UC8rcEBzJSleTkf_-agPM20g`), which is correct.

**The actual problem**: The plugin stores `channel_id` from `validate_channel`. The `check_status` then fetches `/channel/{channel_id}/live`. If YouTube's behavior changed to redirect `/live` to recommended streams, the detection becomes unreliable.

Additional factor: The `cmd_check` command in `main.py:219` passes the raw `channel_id` argument (e.g., `@HakosBaelz`) directly to `check_status`, but `check_status` builds the URL as `/channel/@HakosBaelz/live` — this is wrong. The URL format requires the `UC...` channel ID, not the `@handle`.

## Constraints

### Hard Constraints
- C1: Bilibili `get_status_info_by_uids` API works without authentication — use this as primary validation method
- C2: Bilibili search API and `wbi/acc/info` API require authentication/WBI signing — cannot use for username resolution without cookies
- C3: YouTube handle pages (`/@handle`) do NOT contain `"author"` field — regex `r'"author"\s*:\s*"([^"]+)"'` will never match
- C4: YouTube `/channel/{id}/live` may redirect to other channels' streams — `isLive` check unreliable for determining specific channel's live status
- C5: YouTube `/channel/{id}/live` URL requires `UC...` format channel ID, not `@handle`
- C6: Must not break existing monitors or stored data format
- C7: No API keys available for YouTube Data API v3 (current implementation is scraping-based)

### Soft Constraints
- S1: Bilibili username resolution would require either search API (needs cookie) or a room_id-to-UID mapping — suggest accepting only UID for Bilibili
- S2: YouTube channel display name can be extracted from `<meta property="og:title">` or `<title>` tag on the handle page
- S3: YouTube live status could be more reliably detected by checking `ytInitialData` for active livestream video IDs on the channel page itself

### Dependencies
- D1: Bug 3 fix (YouTube live detection) may require changing the scraping strategy entirely
- D2: Bug 2 fix (channel name) is independent and low-risk

### Risks
- R1: YouTube frequently changes page structure — any HTML scraping solution is inherently fragile
- R2: Bilibili API may start requiring authentication in the future
- R3: YouTube may block server IPs with high request frequency

## Requirements

### REQ-1: Bilibili Username Resolution (Bug 1)

**Scenario**: User runs `/live add bilibili 翼侯大人` or `/live add bilibili @翼侯大人`

**Current**: Returns "channel not found"

**Required**: Either resolve the username to UID and add successfully, OR clearly document that only numeric UIDs are accepted and provide a helpful error message guiding users to find the UID.

**Constraint**: Since Bilibili search/user-info APIs require authentication (C2, C3), the pragmatic approach is:
- Accept numeric UID (already works at API level)
- For non-numeric input, attempt to search via available unauthenticated APIs
- If search unavailable, return clear error message with instructions

### REQ-2: Bilibili Numeric UID Validation (Bug 1)

**Scenario**: User runs `/live add bilibili 2978046`

**Current**: Returns "channel not found" (reported by user)

**Required**: Successfully validates and adds the channel. Debug logging should be added to identify why the API call fails in production if the curl test succeeds.

### REQ-3: YouTube Channel Name Extraction (Bug 2)

**Scenario**: User runs `/live add youtube @HakosBaelz`

**Current**: Channel name falls back to `@HakosBaelz` (the `"author"` regex fails)

**Required**: Extract the actual channel display name (e.g., "Hakos Baelz Ch. hololive-EN") from the handle page.

**Approach**: Use `<title>` tag, `og:title` meta tag, or `"name"` field in `ytInitialData`.

### REQ-4: YouTube Live Status Detection (Bug 3)

**Scenario**: User runs `/live check youtube @HakosBaelz` while channel is live

**Current**: Returns "not live" or returns a different channel's live status due to redirect

**Required**: Correctly detect whether the specific channel is live.

**Sub-issues**:
- `cmd_check` passes `@handle` to `check_status`, which builds invalid URL `/channel/@handle/live` (C5)
- `/live` page redirects may return another channel's stream data (C4)

### REQ-5: cmd_check Channel ID Resolution

**Scenario**: User runs `/live check youtube @HakosBaelz`

**Current**: Passes `@HakosBaelz` directly to `check_status`, which constructs `/channel/@HakosBaelz/live` — invalid URL

**Required**: Resolve `@handle` to `UC...` channel ID before calling `check_status`, or look up the stored channel ID from monitors.

## Success Criteria

- SC-1: `/live add bilibili 2978046` successfully adds the channel and shows the correct username "翼侯大人"
- SC-2: `/live add bilibili 翼侯大人` either resolves to UID and adds, or returns a clear error with instructions to use UID
- SC-3: `/live add youtube @HakosBaelz` shows the channel's display name (not `@HakosBaelz`)
- SC-4: `/live list` shows actual channel display names instead of handles
- SC-5: `/live check youtube @HakosBaelz` correctly detects live status when the channel IS live
- SC-6: No false positives from YouTube redirect behavior
- SC-7: Existing stored monitors continue to work without data migration
