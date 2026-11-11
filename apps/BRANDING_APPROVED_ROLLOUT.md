# Approved TIHULU visual family — staged rollout only

Five artwork variants received **explicit design approval** in the 2026-11-11 conversation:
1. Media Center — screen/play, headphones and waveform
2. Satellite Center — antenna/satellite/orbital elements
3. RF Geolocation Center — coordinate grid, location marker
4. Text Center — subtitle, radio text and information panels
5. Flight Radar — aircraft path and radar field

Common identity: central original TIHULU mascot, red/black/white theme, circular application badge, English product names. Each app must own its approved artwork and asset metadata independently after repository cutover; do not fetch the logo at runtime from the old monorepo.

**Asset format truth:** the uploaded mascot reference was PNG, and the approved illustrations are generated **1254×1254 PNG**, not actual editable SVG vector sources. The chat-side approved logo package includes PNG sizes 512/256/128/64, a manifest and source reference. Its files are **not yet in the GitHub repo** because this PR records only text metadata and no binary upload has been performed. Any future SVG must use actual vector paths (not an SVG wrapper hiding a PNG) and pass side-by-side visual review.

## Rollout stages
1. **Approved design (done):** preserve master PNG hash and user approval in `apps/BRANDING_APPROVED_MANIFEST.json`. All five logos and no others.
2. **Binary asset import (pending):** upload exact approved assets to each app's `branding/` staging folder on a separate reviewed branch. Verify SHA-256 byte identity and license/ownership/provenance. Do not overwrite existing production icons.
3. **True editable SVG (optional but recommended):** vector trace/redraw and compare with approved artwork; maintain source SVG, 16–1024 PNG outputs, metadata and brand guidelines. No downloaded proprietary fonts.
4. **Integration tests:** check desktop launchers/tray/file-icons, Linux .desktop, Windows ICO, macOS ICNS, Qt/Web UI, PWA manifest/scope/service-worker caching, high DPI, light/dark themes, 16–64 px legibility, keyboard/UI accessibility. Names stay English; app interface offers EN/TR/DE.
5. **Non-breaking icon replacement:** only after regression tests and explicit release sign-off, update each app's native icon references and packaging, preserve rollback. Every app carries its own immutable logo files, not a central runtime dependency.
6. **After source repo rename:** verify local icon paths never depend on the old repository name. Any historical brand attribution link uses repo ID and aliases.

## Non-negotiable
No current application icon, executable, installer, generated recording, default or application runtime is changed in this plan. Flight Radar's icon integration takes place in its **already-canonical separate repo**, never through a parallel editable mirror.

## User reconfirmation: only these five red TIHULU mascot designs

The user explicitly confirmed that the previously generated **red/white/black TIHULU emblem family** is the approved set. Do NOT use search-result graphics or substitute a newly created alternate logo. Verified approved ZIP SHA256: `49eeccd46ab8b6e630b5567b4e08c0580f22430696de8e215b80d21a52043f84`. All five 1254px PNG master hashes match `apps/BRANDING_APPROVED_MANIFEST.json`. Destination repo shell mapping: `tihulu-media-center`, `tihulu-satellite-center`, `tihulu-rf-geolocation-center` (empty), plus currently embedded Text Center and already independent Flight Radar. Logo binary imports and live app icon replacements are **not part of this documentation change**.
