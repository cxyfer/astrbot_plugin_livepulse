# Tasks: Fix Bilibili & YouTube Platform Bugs

## Task 1: Fix YouTube channel ID + name extraction in `_resolve_handle` ✅

**File**: `platforms/youtube.py`

**Changes**:
1. Replace `_CHANNEL_ID_RE` with:
   ```python
   _EXTERNAL_ID_RE = re.compile(r'"externalId"\s*:\s*"(UC[\w-]{22})"')
   _OG_URL_CID_RE = re.compile(r'<meta\s+property="og:url"\s+content="https://www\.youtube\.com/channel/(UC[\w-]{22})"', re.I)
   ```
2. Replace `"author"` regex in `_resolve_handle` with:
   ```python
   _OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.I)
   ```
3. Update `_resolve_handle` method:
   - Extract channel ID: `_EXTERNAL_ID_RE` → `_OG_URL_CID_RE` fallback
   - Extract name: `_OG_TITLE_RE` → handle string fallback
4. Update `_get_channel_name` to use same `_OG_TITLE_RE` pattern

**Verification**:
- `@HakosBaelz` → `UCgmPnx-EEeOrZSg5Tiw7ZRQ`, `"Hakos Baelz Ch. hololive-EN"`
- `@EarendelXDFP` → `UCwzpXmWAFEVKH3VzwvSlY_w`, `"Earendel ch. 厄倫蒂兒"`

---

## Task 2: Rewrite YouTube live status detection to use /streams page ✅

**File**: `platforms/youtube.py`

**Changes**:
1. Replace `_LIVE_URL` with:
   ```python
   _STREAMS_URL = "https://www.youtube.com/channel/{channel_id}/streams"
   ```
2. Rewrite `_check_single`:
   - Fetch `/streams` page instead of `/live`
   - Detect live by searching for `"style":"LIVE"` in `thumbnailOverlayTimeStatusRenderer`
   - Extract `videoId` from the matching `videoRenderer` for stream URL
   - Extract title from the matching renderer
   - Extract channel name from `og:title` or `"author"` (available on /streams page)
   - Construct stream URL as `https://www.youtube.com/watch?v={videoId}`
3. Keep `_is_blocked` check for captcha/unusual traffic detection
4. Remove `_THUMB_RE` (thumbnail extraction from new page structure may differ)

**Verification**:
- Channel with active live stream → `is_live=True`, correct title and URL
- Channel with only UPCOMING → `is_live=False`
- Channel with no streams → `is_live=False`

---

## Task 3: Fix cmd_check handle resolution ✅

**File**: `main.py`

**Changes**:
1. In `cmd_check` method (line ~207), before calling `check_status`:
   - If `channel_id` starts with `@` and platform is `youtube`, resolve via `checker.validate_channel`
   - Use the resolved `UC...` ID for `check_status`
   - Also look up channel name from validation result
2. Keep existing behavior for `UC...` format and other platforms

**Verification**:
- `/live check youtube @HakosBaelz` → resolves to correct UC ID, correct live status

---

## Task 4: Fix Bilibili validate_channel with URL support ✅

**File**: `platforms/bilibili.py`

**Changes**:
1. Add regex for URL extraction:
   ```python
   _BILI_URL_RE = re.compile(r'(?:https?://)?live\.bilibili\.com/(\d+)')
   _ROOM_INFO_URL = "https://api.live.bilibili.com/room/v1/Room/get_info"
   ```
2. Rewrite `validate_channel`:
   - Step 1: Check URL pattern → extract room_id → call `_ROOM_INFO_URL` → get UID
   - Step 2: Check if pure numeric → treat as UID → validate via `_API_URL`
   - Step 3: Otherwise → return `None` (caller shows bilibili_hint)
3. Add `_resolve_room_id` helper:
   ```python
   async def _resolve_room_id(self, room_id: str, session: ClientSession) -> str | None:
       # GET room/v1/Room/get_info?room_id={room_id} → data.uid
   ```

**Verification**:
- `2978046` → UID validation → `ChannelInfo(channel_id="2978046", channel_name="翼侯大人")`
- `https://live.bilibili.com/60989` → room 60989 → UID 2978046 → same result
- `翼侯大人` → return None (triggers bilibili_hint)

---

## Task 5: Add Bilibili-specific error message to i18n ✅

**Files**: `i18n/en.json`, `i18n/zh-Hans.json`, `i18n/zh-Hant.json`

**Changes**:
1. Add key `cmd.add.bilibili_hint`:
   - en: `"Bilibili requires a numeric UID or room URL (e.g. live.bilibili.com/60989). Username search is not supported."`
   - zh-Hans: `"Bilibili 需要数字 UID 或直播间链接（如 live.bilibili.com/60989），暂不支持用户名搜索。"`
   - zh-Hant: `"Bilibili 需要數字 UID 或直播間連結（如 live.bilibili.com/60989），暫不支援使用者名稱搜尋。"`
2. Update `main.py` `cmd_add`: when platform is bilibili and `validate_channel` returns None and input is non-numeric non-URL, use `bilibili_hint` instead of generic `invalid_channel`.

**Verification**:
- `/live add bilibili 翼侯大人` → shows bilibili_hint message
- `/live add bilibili 2978046` → does NOT show hint (succeeds)

---

## Task 6: Update proposal.md with findings ✅

**File**: `openspec/changes/fix-bilibili-youtube-bugs/proposal.md`

Update Root Cause Analysis section with the critical discovery that `_CHANNEL_ID_RE` extracts wrong channel IDs from recommended content.

---

## Dependency Order

```
Task 1 (YouTube ID+name) ─┐
                           ├── Task 2 (YouTube live detection) ── Task 3 (cmd_check)
Task 4 (Bilibili)         ─┤
Task 5 (i18n)             ─┘
Task 6 (docs) — independent
```

Tasks 1, 4, 5, 6 can be done in parallel. Task 2 depends on Task 1 (shared regex patterns). Task 3 depends on Task 2.
