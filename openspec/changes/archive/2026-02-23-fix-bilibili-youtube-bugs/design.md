# Design: Fix Bilibili & YouTube Platform Bugs

## Architecture Decisions

### AD-1: YouTube Channel ID Extraction

**Decision**: Replace `_CHANNEL_ID_RE` (first `"channelId"` regex match) with `externalId` from `ytInitialData` + `og:url` fallback.

**Rationale**: The current regex grabs the first `"channelId":"UC..."` on the page, which is often from recommended/related content — verified wrong for both test channels:
- `@HakosBaelz`: got `UC8rcEBzJSleTkf_-agPM20g`, correct is `UCgmPnx-EEeOrZSg5Tiw7ZRQ`
- `@EarendelXDFP`: got `UCFiIsVOC1p_gfTYDYXXfl4g`, correct is `UCwzpXmWAFEVKH3VzwvSlY_w`

**Implementation**:
```python
_EXTERNAL_ID_RE = re.compile(r'"externalId"\s*:\s*"(UC[\w-]{22})"')
_OG_URL_CID_RE = re.compile(r'<meta\s+property="og:url"\s+content="https://www\.youtube\.com/channel/(UC[\w-]{22})"', re.I)
```
Priority: `externalId` → `og:url` → `canonical link`

### AD-2: YouTube Channel Name Extraction

**Decision**: Use `og:title` meta tag instead of `"author"` JSON field.

**Rationale**: Handle pages (`/@handle`) do not contain `"author"` field. `og:title` is verified stable and returns clean display names:
- `@HakosBaelz` → "Hakos Baelz Ch. hololive-EN"
- `@EarendelXDFP` → "Earendel ch. 厄倫蒂兒"

**Implementation**:
```python
_OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.I)
```

### AD-3: YouTube Live Status Detection

**Decision**: Replace `/channel/{id}/live` scraping with `/channel/{id}/streams` page parsing.

**Rationale**: `/live` endpoint redirects to recommended streams from OTHER channels, causing false positives. The `/streams` page contains `thumbnailOverlayTimeStatusRenderer` with `style` field that reliably distinguishes `LIVE`, `UPCOMING`, and `DEFAULT`.

**Implementation**:
- New URL: `https://www.youtube.com/channel/{channel_id}/streams`
- Detection: Search for `"style":"LIVE"` in `thumbnailOverlayTimeStatusRenderer`
- Extract video info (title, videoId, thumbnail) from the matching `videoRenderer`

**Fallback**: If no `LIVE` badge found → channel is offline. No false positives from redirects.

### AD-4: YouTube cmd_check Handle Resolution

**Decision**: In `cmd_check`, resolve `@handle` to `UC...` channel ID before calling `check_status`.

**Rationale**: `check_status` constructs URL with channel_id. Passing `@handle` creates invalid URL `/channel/@handle/streams`.

**Implementation**: Reuse `validate_channel` to resolve, or look up from existing monitors in store.

### AD-5: Bilibili Input Handling

**Decision**: Accept UID (numeric) + URL (`live.bilibili.com/{room_id}`). No username search.

**Rationale**:
- Bilibili search/user-info APIs require authentication (verified)
- `get_status_info_by_uids` (UID) works without auth (verified)
- `room/v1/Room/get_info` (room_id) works without auth, returns UID (verified: room 60989 → UID 2978046)

**Implementation**:
```python
_BILI_URL_RE = re.compile(r'(?:https?://)?live\.bilibili\.com/(\d+)')
```

Input flow:
1. Match URL pattern → extract room_id → call `get_info` API → get UID
2. Pure numeric → treat as UID → validate via `get_status_info_by_uids`
3. Otherwise → error message with usage instructions

### AD-6: Bilibili Room ID to UID API

**Endpoint**: `GET https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}`

**Response**: `data.uid` contains the channel owner's UID.

No authentication required. Verified working.

### AD-7: Existing Monitor Data Handling

**Issue**: Existing YouTube monitors have WRONG channel IDs due to AD-1 bug.

**Decision**: No automatic migration. Users must re-add monitors. The `channel_name` will auto-update on next successful poll via poller's `streamer_name` field.

**Rationale**: Auto-migration requires fetching every stored handle again, which is complex and error-prone. Since the stored channel IDs are wrong, there's no reliable way to map them back to correct IDs without the original `@handle` input.

## File Change Summary

| File | Changes |
|---|---|
| `platforms/youtube.py` | Replace all regex patterns (AD-1, AD-2), rewrite `_check_single` for /streams (AD-3), fix `_resolve_handle` and `_get_channel_name` |
| `platforms/bilibili.py` | Add URL parsing + room_id→UID resolution in `validate_channel` (AD-5, AD-6) |
| `main.py` | Fix `cmd_check` to resolve @handle before check_status (AD-4) |
| `i18n/*.json` | Add `cmd.add.bilibili_hint` error message for non-numeric non-URL input |
