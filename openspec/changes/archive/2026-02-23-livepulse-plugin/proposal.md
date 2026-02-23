# LivePulse - AstrBot Live Stream Monitor Plugin

## Context

### User Need
AstrBot plugin for monitoring live stream status on YouTube, Twitch, and Bilibili. Sends notifications when streamers go live or end streams.

### Reference Materials
- AstrBot plugin development guide: https://docs.astrbot.app/dev/star/plugin-new.html
- AstrBot message event handling: https://docs.astrbot.app/dev/star/guides/listen-message-event.html
- AstrBot message sending: https://docs.astrbot.app/dev/star/guides/send-message.html
- AstrBot plugin configuration: https://docs.astrbot.app/dev/star/guides/plugin-config.html
- Reference plugin (Bilibili only): https://github.com/BB0813/astrbot_plugin_bilibiliobs

### Discovered Constraints

#### Hard Constraints (Technical)
1. **Plugin Structure**: AstrBot Star framework
   - Main class inherits `Star`, decorated with `@register()`
   - Plugin class must be in `main.py`
   - Commands use `@filter.command()` or `@filter.command_group()`
   - Handlers' first two params must be `self` and `event`
   - Handler functions must use `yield event.*_result()` for passive messages
   - Active messages use `await self.context.send_message(unified_msg_origin, MessageChain)`

2. **Async Only**
   - No `requests` library; use `aiohttp` or `httpx`
   - All network I/O must be async

3. **Data Persistence**: must store in `data/` directory (NOT plugin directory)
   - Prevents data loss on plugin update/reinstall
   - Use `os.path.join(os.path.expanduser("~"), ".astrbot", "plugin_name")` pattern

4. **Platform APIs**:
   - **YouTube**: HTML scraping of `youtube.com/channel/{ID}/live` page, checking for `"isLive":true` marker. No API key required. Risk: YouTube may change page structure.
   - **Twitch**: Helix API `GET https://api.twitch.tv/helix/streams?user_login={login}`. Requires Client ID + OAuth Token (Client Credentials grant). User must register a Twitch application.
   - **Bilibili**: Public API `POST https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids` with `{"uids": [...]}`. No auth required. Supports batch queries.

5. **Metadata**: Must provide `metadata.yaml` and `requirements.txt`

6. **Configuration**: `_conf_schema.json` for WebUI config panel. Config injected via `__init__(self, context, config: AstrBotConfig)`.

7. **Command Group**: AstrBot supports `@filter.command_group("name")` with sub-commands via `@group.command("sub")`. Nested groups also supported.

8. **Rich Media**: `MessageChain` supports `.message()` for text, images via `Comp.Image.fromURL()`. Use `event.chain_result([...])` for mixed content.

9. **Group Isolation**: `event.unified_msg_origin` uniquely identifies a session (platform + channel/group). Must be stored per-subscription for active message delivery.

#### Soft Constraints (Conventions)
1. Plugin name starts with `astrbot_plugin_`
2. Code formatted with `ruff`
3. Robust error handling; single error must not crash plugin
4. English commands with per-group language switching for responses

#### Dependencies
- `aiohttp>=3.8.0` - async HTTP
- `beautifulsoup4>=4.12.0` - YouTube HTML parsing (for `isLive` detection)

## Requirements

### R1: Multi-Platform Live Stream Monitoring
**Scenario**: Users can monitor live channels across different platforms
- **R1.1**: YouTube channel monitoring via HTML scraping (`/channel/{ID}/live`)
- **R1.2**: Twitch channel monitoring via Helix API (`streams` endpoint)
- **R1.3**: Bilibili user monitoring via public batch API
- **R1.4**: Each platform has independent polling interval (configurable globally via WebUI, overridable per-group via command)

### R2: Command System (Command Group: `/live`)
**Scenario**: Users manage monitors via English command group
- **R2.1**: `/live add <platform> <channel_id>` - Add monitor to current group
- **R2.2**: `/live remove <platform> <channel_id>` - Remove monitor from current group
- **R2.3**: `/live list` - List monitors for current group (with live status)
- **R2.4**: `/live check <platform> <channel_id>` - Check specific channel status (one-off, no subscription needed)
- **R2.5**: `/live interval <platform> <seconds>` - Override polling interval for current group
- **R2.6**: `/live lang <en|zh>` - Switch response language for current group
- **R2.7**: `/live notify <on|off>` - Toggle notifications for current group
- **R2.8**: `/live end_notify <on|off>` - Toggle end-of-stream notifications for current group
- **R2.9**: `/live status` - Show plugin status (task health, session count, etc.)

### R3: Live Stream Notification
**Scenario**: Automatic notification when streamer goes live
- **R3.1**: Notification includes: streamer name, title, category (if available), link, cover thumbnail (image)
- **R3.2**: No duplicate notifications (track `last_status` per monitor per group)
- **R3.3**: End-of-stream notification (toggleable per group, default on)
- **R3.4**: On first startup or when adding a monitor that is already live, do NOT send notification (prevents spam)
- **R3.5**: Cover thumbnail uses `Comp.Image.fromURL()`. If image sending fails, fallback to text-only.

### R4: Per-Group Isolation
**Scenario**: Each group/channel independently manages its own monitors and settings
- **R4.1**: Monitor lists are per-group (keyed by `unified_msg_origin`)
- **R4.2**: Language setting is per-group
- **R4.3**: Notification toggles are per-group
- **R4.4**: Polling interval override is per-group (falls back to global default)

### R5: Multi-Language Support
**Scenario**: Users can switch bot response language per group
- **R5.1**: Support English (en) and Chinese (zh)
- **R5.2**: All command responses and notifications respect group language setting
- **R5.3**: i18n strings stored in separate JSON files
- **R5.4**: Default language configurable via WebUI

### R6: Configuration Management (WebUI via `_conf_schema.json`)
**Scenario**: Plugin settings managed via AstrBot WebUI
- **R6.1**: Twitch `client_id` and `client_secret` (string)
- **R6.2**: Default polling intervals per platform (int, seconds)
- **R6.3**: Default language (string, options: en/zh)
- **R6.4**: Max monitors per group (int, default 30)
- **R6.5**: Enable notifications globally (bool, default true)
- **R6.6**: Enable end-of-stream notifications globally (bool, default true)
- **R6.7**: Include cover thumbnail in notifications (bool, default true)

### R7: Error Handling & Resilience
**Scenario**: Plugin remains stable under adverse conditions
- **R7.1**: API errors handled gracefully; single channel error does not interrupt others
- **R7.2**: Network timeout handling (default 15s)
- **R7.3**: Rate limit detection with dynamic backoff (Bilibili 429, Twitch 429, YouTube page block)
- **R7.4**: Exponential backoff on consecutive errors per channel
- **R7.5**: Proper resource cleanup on plugin terminate (cancel tasks, close sessions)
- **R7.6**: Bilibili batch query to reduce API pressure

### R8: Per-Platform Polling Architecture
**Scenario**: Each platform runs its own independent polling loop
- **R8.1**: Separate `asyncio.Task` per platform (YouTube, Twitch, Bilibili)
- **R8.2**: Each task aggregates all monitored channels across all groups for that platform
- **R8.3**: After status check, dispatch notifications to each relevant group
- **R8.4**: Tasks gracefully restart on unrecoverable error

## Success Criteria

### SC1: Functional
- [ ] `/live add youtube <channel_id>` adds YouTube monitor to current group
- [ ] `/live add twitch <username>` adds Twitch monitor to current group
- [ ] `/live add bilibili <uid>` adds Bilibili monitor to current group
- [ ] `/live remove` correctly removes monitors
- [ ] `/live list` shows current group's monitors with live status
- [ ] Notification sent to correct group when streamer goes live
- [ ] No duplicate notifications on same live session
- [ ] End-of-stream notification works when enabled
- [ ] `/live lang zh` switches responses to Chinese for that group
- [ ] `/live lang en` switches back to English

### SC2: Performance
- [ ] Each platform polls independently at its configured interval
- [ ] Bilibili uses batch query for multiple UIDs
- [ ] Single channel error does not block other channels or platforms

### SC3: Reliability
- [ ] Plugin restart restores all monitor subscriptions
- [ ] Rate limiting triggers automatic backoff
- [ ] Network errors do not crash plugin
- [ ] `terminate()` properly cancels all tasks and closes HTTP sessions

### SC4: Group Isolation
- [ ] Group A's monitors do not appear in Group B's list
- [ ] Group A's language setting does not affect Group B
- [ ] Removing a monitor in Group A does not affect Group B's identical monitor

## Resolved Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Notification target | Group where `/live add` was issued | Per-group isolation |
| Multi-group isolation | Yes, fully isolated per `unified_msg_origin` | User preference |
| End-of-stream notification | Supported, toggleable per group | Feature parity with reference |
| First startup behavior | If already live, do NOT notify | Prevent spam on startup |
| YouTube detection method | HTML scraping of `/channel/{ID}/live` | Free, no API key, no quota |
| Twitch authentication | User provides Client ID + Client Secret in WebUI | Twitch requires OAuth |
| Bilibili authentication | Public API, no auth | Simplest approach |
| Permission management | All commands open to all users | Simplicity |
| Error reporting | Log only, no proactive notification to users | Simplicity |
| Cover thumbnail | Include in notification, fallback to text if fails | User preference |
| Max monitors per group | Configurable via WebUI, default 30 | User preference |
| Language scope | Per-group setting | User preference |
| Command structure | Command group (`/live` with sub-commands) | User preference, AstrBot native support |

## Technical Design Notes

### Platform Identifiers
- `youtube` - YouTube channel (input: channel ID like `UCxxxxx`)
- `twitch` - Twitch channel (input: username like `shroud`)
- `bilibili` - Bilibili user (input: UID like `12345`)

### Default Polling Intervals
- YouTube: 300s (5 min) - HTML scraping, conservative to avoid blocks
- Twitch: 120s (2 min) - API with proper auth
- Bilibili: 180s (3 min) - Public API, moderate rate

### Data Structure (persisted as JSON)
```json
// ~/.astrbot/livepulse/data.json
{
  "groups": {
    "<unified_msg_origin>": {
      "language": "en",
      "notify_enabled": true,
      "end_notify_enabled": true,
      "interval_overrides": {},
      "monitors": {
        "youtube": {
          "<channel_id>": {"name": "", "last_status": false, "last_stream_id": ""}
        },
        "twitch": {
          "<username>": {"name": "", "last_status": false, "last_stream_id": ""}
        },
        "bilibili": {
          "<uid>": {"name": "", "last_status": false, "last_title": ""}
        }
      }
    }
  }
}
```

### YouTube Detection Method
1. `GET https://www.youtube.com/channel/{CHANNEL_ID}/live`
2. Parse HTML response for `"isLive":true` or `hqdefault_live.jpg`
3. Extract stream title from page metadata if live
4. Extract thumbnail URL from page metadata
5. Fallback: if page structure changes, log warning and skip

### Twitch Detection Method
1. Use Client Credentials OAuth flow to get app access token
2. `GET https://api.twitch.tv/helix/streams?user_login={username}`
3. If `data` array is non-empty, user is live
4. Extract: `title`, `game_name`, `thumbnail_url`, `user_name`
5. Token auto-refresh on expiry

### Bilibili Detection Method
1. `POST https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids`
2. Body: `{"uids": [uid1, uid2, ...]}`
3. `live_status == 1` means live
4. Extract: `uname`, `title`, `room_id`, `cover_from_user`
5. Batch all UIDs across all groups in single request

### File Structure
```
astrbot_plugin_livepulse/
├── main.py              # Plugin class with command group and polling tasks
├── metadata.yaml        # Plugin metadata
├── requirements.txt     # Dependencies
├── _conf_schema.json    # WebUI config schema
└── i18n/
    ├── en.json          # English strings
    └── zh.json          # Chinese strings
```

### Polling Architecture
```
Plugin init
├── Task: youtube_poller (aggregates all YouTube monitors across groups)
├── Task: twitch_poller  (aggregates all Twitch monitors across groups)
└── Task: bilibili_poller (aggregates all Bilibili monitors across groups)

Each poller:
1. Collect all unique channel IDs from all groups
2. Batch query status
3. For each group that monitors a changed channel:
   - Check if status changed (was offline -> now live, or vice versa)
   - Send notification to that group's unified_msg_origin
4. Update persisted state
5. Sleep for platform interval
```
