# Specs: Bilibili Platform Fixes

## SPEC-BL-1: UID Validation

**Invariant**: `get_status_info_by_uids` API returns valid data for existing UIDs without authentication.

**Property**: Numeric input that is a valid Bilibili UID must successfully validate and return `ChannelInfo` with correct `channel_name`.

**Falsification**: `/live add bilibili 2978046` → must add successfully with name `"翼侯大人"`.

**Boundary**:
- UID exists but has no live room → `get_status_info_by_uids` returns data with `room_id=0`, should still validate successfully
- UID does not exist → API returns no data for that key → return None

## SPEC-BL-2: URL Input (Room ID Resolution)

**Invariant**: `room/v1/Room/get_info?room_id={id}` returns `data.uid` for valid room IDs.

**Property**: URL input `live.bilibili.com/{room_id}` must extract room_id, resolve to UID via API, then validate UID.

**Falsification**: `/live add bilibili https://live.bilibili.com/60989` → must resolve room 60989 to UID 2978046, then add with name `"翼侯大人"`.

**Accepted URL formats**:
- `live.bilibili.com/60989`
- `https://live.bilibili.com/60989`
- `http://live.bilibili.com/60989`

**Boundary**:
- Room ID does not exist → API returns error → return None with "channel not found"
- Room ID is 0 → skip, return error

## SPEC-BL-3: Non-Numeric Non-URL Input Handling

**Invariant**: Non-numeric, non-URL input cannot be resolved without authenticated APIs.

**Property**: Input like `翼侯大人` or `@翼侯大人` must return a specific error message guiding user to provide UID or room URL.

**Falsification**: `/live add bilibili 翼侯大人` → must return `cmd.add.bilibili_hint` message, NOT generic `cmd.add.invalid_channel`.
