<div align="center">

<img src="logo.png" width="300" alt="LivePulse Logo">

# 🔔 LivePulse

*AstrBot plugin for monitoring live streams on YouTube, Twitch, and Bilibili. Sends notifications when streamers go live or end streams.*

[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg?style=flat-square)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat-square&logo=python)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg?style=flat-square)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/Author-Xyfer-ff69b4?style=flat-square)](https://github.com/cxyfer)

</div>

---

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

> [!IMPORTANT]
> Twitch account must have **Two-Factor Authentication (2FA)** enabled before creating an application.

<details>
<summary>Twitch setup — obtaining Client ID & Secret</summary>

Twitch monitoring requires a [Twitch Developer Application](https://dev.twitch.tv/console).

1. Go to the [Twitch Developer Console](https://dev.twitch.tv/console)
2. Log in with your Twitch account
3. Click **Register Your Application**
4. Fill in the form:
   - **Name** — any name (e.g. `LivePulse`)
   - **OAuth Redirect URLs** — `http://localhost`
   - **Category** — `Chat Bot`
   - **Client Type** — `Confidential`
5. After creation, open the application details to copy the **Client ID**
6. Click **New Secret** to generate a **Client Secret**
7. Enter both values in the AstrBot WebUI plugin configuration

</details>

> [!NOTE]
> YouTube and Bilibili require no credentials.

## Commands

All commands are under the `/live` command group.

| Command | Description |
|---------|-------------|
| `/live add <platform> <channel_id> [<channel_id>...]` | Add monitor(s) |
| `/live add <url> [<url>...]` | Add monitor(s) (auto-detect platform) |
| `/live remove <platform> <channel_id> [<channel_id>...]` | Remove monitor(s) |
| `/live remove <url> [<url>...]` | Remove monitor(s) (auto-detect platform) |
| `/live list` | List monitors with current status |
| `/live check <platform> <channel_id>` | One-off status check |
| `/live lang <en\|zh-Hans\|zh-Hant>` | Switch response language |
| `/live notify <on\|off>` | Toggle live-start notifications |
| `/live end_notify <on\|off>` | Toggle end-of-stream notifications |
| `/live status` | Show plugin health and stats |
| `/live test_notify <delay>` | Send simulated notifications after `<delay>` seconds (max 300) |

**Platform identifiers:** `youtube`, `twitch`, `bilibili`

**Supported channel ID formats:**

| Platform | Accepted Formats | Examples |
|----------|-----------------|----------|
| YouTube | `@handle`, `channel_id`, or URL | `@GawrGura`, `UCoSrY_IQQVpmIRZ9Xf-y93g`, `https://www.youtube.com/@GawrGura` |
| Twitch | `username` or URL | `shroud`, `https://www.twitch.tv/shroud` |
| Bilibili | `UID` or URL | `672328094`, `https://live.bilibili.com/22637261` |

> [!NOTE]
> When using a URL, no platform argument is needed — the platform is auto-detected from the hostname.

**Examples:**

```
# Single add
/live add youtube @GawrGura
/live add twitch shroud
/live add bilibili 672328094
/live add https://live.bilibili.com/22637261

# Batch add (up to 20)
/live add youtube @NanashiMumei @GawrGura
/live add twitch shroud pokimane
/live add bilibili 672328094 22637261
/live add https://www.youtube.com/@GawrGura https://live.bilibili.com/22637261

# Remove
/live remove https://www.youtube.com/@GawrGura
/live remove youtube @GawrGura

# Other commands
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

[GNU Affero General Public License v3.0](LICENSE)
