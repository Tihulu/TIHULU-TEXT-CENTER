# English engineering, trilingual interface policy for every TIHULU app

Every eventual independent application must support **English (en), Turkish (tr) and German (de)** in its user interface. English remains the default **UI language** for the new independent release unless the user selects another language. **All implementation, architecture contracts, internal logic, tests, PR titles/descriptions, developer prompts and source code comments are written in English.**

## Distinct layers
- UI localization: visible menus, dialogs, status, settings, notifications, accessibility labels, dates, units and errors. Implement with translatable message keys and local offline resource bundles.
- Content and AI translation: spoken captions/Whisper, local NLLB/Argos/MADLAD models, Teletext/DLS and preserved original-language text. **Not the same as UI localization.** No new model installed solely for UI language support.
- Machine-readable data: stable English keys and versioned file/API schemas. Do not translate JSON keys, frequency bands, timestamps, protocol names or resource IDs.

## Implementation readiness (future, not this PR)
1. Inspect existing labels and built-in language settings per app. Preserve current actual default behavior until a separately tested UI change; do not imply translation completeness.
2. Extract strings into offline locale bundles `locales/en`, `locales/tr`, `locales/de` (format appropriate to chosen framework: gettext, Fluent, Qt .ts etc.). Include pluralization/interpolation, units and accessibility.
3. Provide explicit locale selection with saved preference and safe English fallback for missing keys. Respect user-selected locale across app updates and independent repo migrations.
4. Test RTL-independent layouts for Turkish dotted/dotless I and German compound word expansion; test keyboard/touch labels and fullscreen. Avoid using text lookup in business logic.
5. Block claims of completed trilingual interface until actual UI coverage and user acceptance checks are recorded for **all three**.

**Current state:** required scope documented; translations and locale switches are **not implemented or changed by this repository preparation PR**.
