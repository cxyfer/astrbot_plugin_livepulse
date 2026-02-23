# multi-language Specification

## Purpose
TBD - created by archiving change livepulse-plugin. Update Purpose after archive.
## Requirements
### Requirement: English and Chinese language support
The system SHALL support English (`en`) and Chinese (`zh`) for all command responses and notifications. Language strings SHALL be stored in separate JSON files under `i18n/`.

#### Scenario: English response
- **WHEN** a group's language is set to `en`
- **THEN** all command responses and notifications SHALL use strings from `i18n/en.json`

#### Scenario: Chinese response
- **WHEN** a group's language is set to `zh`
- **THEN** all command responses and notifications SHALL use strings from `i18n/zh.json`

### Requirement: i18n fallback mechanism
If a message key is missing in the group's configured language file, the system SHALL fall back to `en.json`.

#### Scenario: Missing key fallback
- **WHEN** the group's language is `zh`
- **AND** a required message key exists in `en.json` but not in `zh.json`
- **THEN** the system SHALL use the English string from `en.json`

#### Scenario: All keys present
- **WHEN** both `en.json` and `zh.json` contain all required message keys
- **THEN** the system SHALL use the string from the group's configured language file

### Requirement: Default language from WebUI config
The default language for new groups SHALL be configurable via WebUI. The default value is `en`.

#### Scenario: New group uses default language
- **WHEN** a user first interacts with the plugin in a new group
- **THEN** the group's language SHALL be set to the WebUI-configured default language

#### Scenario: Default language changed
- **WHEN** an administrator changes the default language in WebUI to `zh`
- **THEN** new groups created after the change SHALL default to `zh`
- **AND** existing groups SHALL retain their current language setting

