# TIHULU TEXT CENTER — Text & Alerts UI/UX Consolidation

**Date:** 2026-11-06
**Integration parent:** PR #15 (Radio / TV Center)
**Scope:** UI/navigation and existing archive reading **only**.

## Product decision

Replace the fragmented main navigation entries *Weather Text*, *Emergency* and
*Text Networks* with one **Text & Alerts** destination (legacy page 500).
The old page 300 and page 800 routes remain accessible from inside Text & Alerts
and via numeric navigation. This must not delete previously recorded text or
rebuild decoder pipelines.

The desired reader uses an actual-purpose workflow:

**Choose source category → Search received items → Read full text →
Inspect provenance / source / timestamp → Open related numbered page.**

### Existing decoder sources already supported by archive format

| Category | Decoder-attributed media |
| --- | --- |
| Radio Text | `fm_rds`, `dab_dls`, `drm` |
| Teletext & Journaline | `dvb_teletext`, `journaline` pages |
| Weather & maritime | `navtex`, `hf_weather` |
| Other text | `aprs`, `other_receiver` |
| Cached Internet | RSS/Atom articles from `/api/articles` |

Text & Alerts reads existing `/api/events`, `/api/pages` and
`/api/articles` data. Full numbered pages are fetched from `/api/page`
**only after a user selects them**. User text is rendered using
`textContent` rather than injection of untrusted markup. Search and filters
are local to the loaded archive; no receiver starts on opening the page, and
no automatic background fetch loop is added.

Selected pages can be navigated to previous/next page within their source;
their page numbers and source_id remain intact, with the pre-existing
numeric-page viewer also available as a separate action. News articles are
shown as **cached Internet**, never falsely as antenna received messages.

## Emergency integrity

An RF-received text item, Teletext message or news article is NOT a verified
live official emergency alert. This UI does **not** scrape arbitrary text for
hazard words and assign urgency/severity. The *Emergency guidance* filter
explains the boundary and gives plain links to relevant official agencies.

Authentic future alert integration should use opt-in CAP 1.2 feeds from
explicitly approved authority endpoints, with authenticated source identity,
sent/effective/expires times, status/update/cancellation semantics, warning
region, language, and strict separation from inferred or crowd-sourced data.
Until implemented, never render 'No warnings in your area' or pretend alert
monitoring is operating.

Relevant public specifications:
- WMO/OASIS CAP: https://wmo.int/site/wmo-common-alerting-protocol
- Enhanced Teletext: https://www.etsi.org/deliver/etsi_i_ets/300700_300799/300706/01_60/ets_300706e01p.pdf

## Strict TV / hardware boundaries

- **DO NOT MODIFY** the TV application's existing Teletext feature, viewer,
  decoder, page selection, TV session controls, tuner driver, firmware,
  `dvbv5-scan`, MPEG-TS relay, media player or recording path.
- The user is currently testing Hauppauge DVB driver/firmware separately; this
  branch intentionally does not depend on, modify or claim successful tests.
- The new Text & Alerts is an independent *archive reader* of whatever a
  previously authorized decoder has already imported. Lack of decoded pages
  displays an honest empty state.
- Other Tihulu standalone apps (Flight Radar, Satellite Center, Survival Kit,
  and their repos) remain untouched and will be connected by their own active
  developments. Do not replace their implementations with empty placeholders.

## Cross-platform parity

Local desktop/web-with-companion receives the full archive reader, using
the existing local API; GitHub Pages receives a matching **Text & Alerts**
navigation entry and a clear link to the locally running reader. Static Pages
has no direct access to PC SQLite or arbitrary local processes; it must not
claim standalone Teletext, DAB decoder, CAP or TV hardware access. Mobile
`127.0.0.1` is the mobile device, so remote access requires a separate
authenticated LAN gateway.

## Validation

`node --check web/app.js`, `node --check docs/pages.js`,
`python -m unittest discover -s tests -v`, GitHub Actions platform smoke tests.
Physical RF or TV driver acceptance is explicitly out of scope. Retain all
other PR #13-15 features, English language defaults and global HARD STOP.

The feature remains a Draft PR until UI regressions and live receiver
integration are validated.
