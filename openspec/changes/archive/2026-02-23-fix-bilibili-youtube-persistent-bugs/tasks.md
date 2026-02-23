## 1. Shared User-Agent Constant

- [x] 1.1 Define `DEFAULT_USER_AGENT` constant in `platforms/__init__.py` with a Chrome desktop UA string
- [x] 1.2 Update `main.py:59` to initialize `aiohttp.ClientSession(headers={"User-Agent": DEFAULT_USER_AGENT})`
- [x] 1.3 Replace hardcoded `_USER_AGENT` in `youtube.py:12` with import from `platforms.DEFAULT_USER_AGENT`
- [x] 1.4 Update YouTube per-request header construction (`youtube.py:43,127,153`) to use the imported constant

## 2. Fix YouTube `_is_blocked()`

- [x] 2.1 Replace `_is_blocked()` body in `youtube.py:165-166`: remove `"captcha"` check, keep only `"unusual traffic" in html.lower()`

## 3. Surface RateLimitError in `cmd_add`

- [x] 3.1 Add `except RateLimitError as e:` clause before `except Exception` in `cmd_add` (`main.py:151`), yielding `error.rate_limited` with `platform=e.platform`
- [x] 3.2 Add `RateLimitError` import to `main.py` from `platforms.base`

## 4. i18n Updates

- [x] 4.1 Add `error.rate_limited` key to `i18n/en.json`: `"{platform} is currently rate-limiting requests. Please try again later."`
- [x] 4.2 Add `error.rate_limited` key to `i18n/zh-Hans.json`: `"{platform} 目前正在限制请求频率，请稍后再试。"`
- [x] 4.3 Add `error.rate_limited` key to `i18n/zh-Hant.json`: `"{platform} 目前正在限制請求頻率，請稍後再試。"`

## 5. Verification

- [x] 5.1 Verify no duplicate UA string literals remain in codebase (`rg` for hardcoded Chrome UA strings)
- [x] 5.2 Verify `_is_blocked()` returns `False` for HTML containing only `captcha`/`grecaptcha` (no `unusual traffic`)
- [x] 5.3 Verify `_is_blocked()` returns `True` for HTML containing `unusual traffic`
- [x] 5.4 Verify `cmd_add` with stubbed `RateLimitError` yields `error.rate_limited`, not `cmd.add.invalid_channel`
- [x] 5.5 Verify Twitch checker still functions correctly with session-level UA (headers merge, no conflict)
