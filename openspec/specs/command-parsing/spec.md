## ADDED Requirements

### Requirement: Notify command argument parsing
The system SHALL extract the `on`/`off` argument from `cmd_notify` and `cmd_end_notify` using `_parse_batch_args()` rather than raw string splitting.

#### Scenario: User sends `live notify on`
- **WHEN** `event.message_str` is `"live notify on"`
- **THEN** `_parse_batch_args(event, "notify")` returns `["on"]` and `arg = "on"`
- **THEN** notification state is set to enabled

#### Scenario: User sends `live end_notify off`
- **WHEN** `event.message_str` is `"live end_notify off"`
- **THEN** `_parse_batch_args(event, "end_notify")` returns `["off"]` and `arg = "off"`
- **THEN** end-notification state is set to disabled

#### Scenario: User sends command without argument
- **WHEN** `event.message_str` is `"live notify"` (no trailing arg)
- **THEN** `_parse_batch_args(event, "notify")` returns `[]` and `arg = None`
- **THEN** handler returns current status without mutation

#### Scenario: User sends invalid argument
- **WHEN** `event.message_str` is `"live notify foo"`
- **THEN** `arg = "foo"` which matches neither `"on"` nor `"off"`
- **THEN** handler returns invalid-argument response without mutation
