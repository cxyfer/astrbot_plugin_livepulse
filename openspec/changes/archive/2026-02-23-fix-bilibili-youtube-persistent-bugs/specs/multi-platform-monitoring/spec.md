## ADDED Requirements

### Requirement: Shared HTTP session MUST include browser-like User-Agent
The shared `aiohttp.ClientSession` SHALL be initialized with a default `User-Agent` header set to the value of `DEFAULT_USER_AGENT` defined in `platforms/__init__.py`. All platform checkers using the shared session SHALL inherit this header automatically. The User-Agent value SHALL be a standard desktop Chrome browser string.

#### Scenario: Bilibili API accepts requests with shared session UA
- **WHEN** the Bilibili checker sends a POST to `get_status_info_by_uids` via the shared session
- **THEN** the request SHALL include a `User-Agent` header equal to `DEFAULT_USER_AGENT`
- **AND** Bilibili SHALL NOT return HTTP 412

#### Scenario: Bilibili room resolution uses shared session UA
- **WHEN** the Bilibili checker sends a GET to `get_info?room_id=X` via the shared session
- **THEN** the request SHALL include the session-level `User-Agent` header

#### Scenario: Per-request headers merge with session defaults
- **WHEN** a platform checker (e.g., YouTube) provides per-request headers
- **THEN** those headers SHALL merge with (not replace) the session-level `User-Agent`
- **AND** if per-request headers include `User-Agent`, the per-request value SHALL take precedence

#### Scenario: Twitch API unaffected by session-level UA
- **WHEN** the Twitch checker sends requests with `Client-ID` and `Authorization` headers via the shared session
- **THEN** the session-level `User-Agent` SHALL also be sent
- **AND** the Twitch API SHALL respond normally (UA does not conflict with OAuth headers)

### Requirement: Single source of truth for User-Agent constant
The `DEFAULT_USER_AGENT` constant SHALL be defined in `platforms/__init__.py`. Both the session initialization in `main.py` and any per-request header construction (e.g., YouTube) SHALL import from this single location. No duplicate UA string literals SHALL exist across the codebase.

#### Scenario: YouTube per-request UA matches session default
- **WHEN** YouTube constructs per-request headers with a User-Agent
- **THEN** the value SHALL be imported from `DEFAULT_USER_AGENT` in `platforms/__init__.py`
- **AND** no hardcoded UA string SHALL exist in `youtube.py`
