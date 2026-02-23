# LivePulse

AstrBot plugin for monitoring live streams on YouTube, Twitch, and Bilibili. Sends notifications when streamers go live or end streams.

## Features

- **Multi-platform** — YouTube (HTML scraping), Twitch (Helix API), Bilibili (batch API)
- **Per-group isolation** — each group manages its own monitors, language, and notification settings
- **Smart polling** — per-platform independent polling with deduplication, exponential backoff, and rate limit handling
- **i18n** — English, Simplified Chinese, Traditional Chinese, switchable per group
- **Reliable persistence** — atomic JSON writes with crash recovery and `.bak` fallback
- **Auto-disable** — notifications auto-disabled after 10 consecutive delivery failures

## Installation

```bash
# In AstrBot plugins directory
cd ~/.astrbot/data/plugins/
git clone https://github.com/cxyfer/astrbot_plugin_livepulse
```

Or paste the repo URL in AstrBot WebUI plugin management page.

## Configuration

After installation, configure in AstrBot WebUI:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `twitch_client_id` | string | `""` | Twitch API Client ID |
| `twitch_client_secret` | string | `""` | Twitch API Client Secret |
| `youtube_interval` | int | `300` | YouTube polling interval (seconds) |
| `twitch_interval` | int | `120` | Twitch polling interval (seconds) |
| `bilibili_interval` | int | `180` | Bilibili polling interval (seconds) |
| `default_language` | string | `"en"` | Default language for new groups |
| `max_monitors_per_group` | int | `30` | Max monitors per group |
| `max_global_channels` | int | `500` | Max unique channels globally |
| `enable_notifications` | bool | `true` | Global live-start notifications |
| `enable_end_notifications` | bool | `true` | Global end-of-stream notifications |
| `include_thumbnail` | bool | `true` | Include thumbnail in notifications |

> Twitch monitoring requires a [Twitch Developer Application](https://dev.twitch.tv/console). YouTube and Bilibili require no credentials.

## Commands

All commands are under the `/live` command group.

| Command | Description |
|---------|-------------|
| `/live add <platform> <channel_id>` | Add a monitor (supports YouTube `@handle`) |
| `/live remove <platform> <channel_id>` | Remove a monitor |
| `/live list` | List monitors with current status |
| `/live check <platform> <channel_id>` | One-off status check |
| `/live lang <en\|zh-Hans\|zh-Hant>` | Switch response language |
| `/live notify <on\|off>` | Toggle live-start notifications |
| `/live end_notify <on\|off>` | Toggle end-of-stream notifications |
| `/live status` | Show plugin health and stats |

**Platform identifiers:** `youtube`, `twitch`, `bilibili`

**Examples:**
```
/live add youtube @PewDiePie
/live add twitch shroud
/live add bilibili 672328094
/live list
/live lang zh-Hant
```

## Architecture

```
astrbot_plugin_livepulse/
├── main.py              # Entry point, lifecycle, command handlers
├── core/
│   ├── models.py        # Data models (GroupState, MonitorEntry, StatusSnapshot)
│   ├── store.py         # In-memory state with asyncio.Lock
│   ├── persistence.py   # Atomic JSON persistence with crash recovery
│   ├── poller.py        # Per-platform polling engine
│   └── notifier.py      # Notification dispatch with failure tracking
├── platforms/
│   ├── base.py          # BasePlatformChecker ABC
│   ├── youtube.py       # YouTube HTML scraper + @handle resolver
│   ├── twitch.py        # Twitch Helix API + OAuth token manager
│   └── bilibili.py      # Bilibili batch API
└── i18n/
    ├── en.json          # English strings
    ├── zh-Hans.json     # Simplified Chinese strings
    └── zh-Hant.json     # Traditional Chinese strings
```

## License

MIT
