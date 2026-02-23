# Specs: YouTube Platform Fixes

## SPEC-YT-1: Channel ID Resolution from Handle Page

**Invariant**: `externalId` in `ytInitialData` always matches the page owner's canonical channel ID.

**Property**: For any `@handle`, the resolved channel ID must equal the `externalId` field, NOT the first `"channelId"` match.

**Falsification**: Resolve `@HakosBaelz` — must return `UCgmPnx-EEeOrZSg5Tiw7ZRQ`, not `UC8rcEBzJSleTkf_-agPM20g`.

**Boundary**:
- Handle that doesn't exist → return None
- Handle page blocked (captcha/unusual traffic) → raise RateLimitError
- `externalId` missing from page → fallback to `og:url` extraction

## SPEC-YT-2: Channel Name Extraction

**Invariant**: `og:title` meta tag on handle/channel pages contains the display name.

**Property**: Extracted name must be a non-empty string, not the raw handle.

**Falsification**: Resolve `@EarendelXDFP` → must return `"Earendel ch. 厄倫蒂兒"`, not `"@EarendelXDFP"`.

**Boundary**:
- `og:title` missing → fallback to `<title>` tag with ` - YouTube` suffix stripped
- Both missing → fallback to handle string

## SPEC-YT-3: Live Status Detection via /streams

**Invariant**: The `/streams` page's `thumbnailOverlayTimeStatusRenderer.style` field reliably indicates `LIVE`, `UPCOMING`, or `DEFAULT`.

**Property**: A channel is live IFF the /streams page contains at least one entry with `"style":"LIVE"`.

**Falsification**:
- Channel with UPCOMING stream only → must NOT report as live
- Channel with no streams → must report offline
- Channel actively live → must report as live with correct title and stream URL

**Boundary**:
- Page returns captcha/blocked → raise RateLimitError, do NOT report offline
- Page has `LIVE` + `UPCOMING` entries → report live (first LIVE entry)

## SPEC-YT-4: cmd_check Handle Resolution

**Invariant**: `check_status` receives only `UC...` format channel IDs.

**Property**: When user passes `@handle` to `/live check`, it must be resolved to `UC...` ID before API call.

**Falsification**: `/live check youtube @HakosBaelz` must NOT construct URL `/channel/@HakosBaelz/streams`.
