## 1. i18n Updates

- [x] 1.1 Update `i18n/en.json`: modify `notify.embed.live_title`, `notify.embed.end_title`, `notify.embed.field.platform`, `notify.embed.field.category` to new values; add `notify.embed.footer` and `notify.embed.field.link` keys
- [x] 1.2 Update `i18n/zh-Hans.json`: same key modifications and additions as en.json with simplified Chinese values
- [x] 1.3 Update `i18n/zh-Hant.json`: same key modifications and additions as en.json with traditional Chinese values
- [x] 1.4 Verify all 3 locale files have identical embed key sets and correct `{name}`/`{id}` placeholders

## 2. display_id Propagation

- [x] 2.1 Add `display_id: str = ""` field to `_PendingNotification` dataclass in `core/poller.py`
- [x] 2.2 Populate `display_id=entry.display_id` when constructing `_PendingNotification` in the poller loop
- [x] 2.3 Pass `display_id=note.display_id` in the `send_end_notification` call within the poller dispatch block

## 3. Notifier Core Logic

- [x] 3.1 Add private helper `_truncate_title(self, template: str, name: str) -> str` to `Notifier` — computes budget from `template.format(name="")`, truncates name with `…` if over budget, returns formatted title
- [x] 3.2 Add `display_id: str = ""` parameter to `send_end_notification` and pass it through to `_build_end_embed`
- [x] 3.3 Refactor `_build_live_embed`: use `_truncate_title` for title, render footer from `notify.embed.footer` i18n key with `name` and `id` (using `snapshot.display_id or snapshot.streamer_name` as fallback), add `strip()` to category/stream_url checks, add conditional Link field with `notify.embed.field.link` i18n key
- [x] 3.4 Refactor `_build_end_embed`: accept `display_id` parameter, use `_truncate_title` for title, render footer from `notify.embed.footer` i18n key with `name` and `id` (using `display_id or streamer_name` as fallback)

## 4. test_notify Update

- [x] 4.1 Update `_run_test_notify` in `main.py`: add `display_id="TestStreamer"` to the test `StatusSnapshot`, pass `display_id="TestStreamer"` to `send_end_notification`

## 5. Verification

- [ ] 5.1 Run `test_notify` command on a Discord channel to confirm live-start embed renders correctly (title with name, emoji fields, footer with name+ID, Link field)
- [ ] 5.2 Confirm live-end embed renders correctly (title with name, single Platform field, footer with name+ID)
- [ ] 5.3 Confirm plain-text notification path is unaffected (test on a non-Discord platform or with `DiscordEmbed=None`)
