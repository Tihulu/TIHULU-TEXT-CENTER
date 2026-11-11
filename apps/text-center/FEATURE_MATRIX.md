# text-center — behavior preservation matrix

Source of truth for mapping existing features across languages/frameworks: [FEATURE_MATRIX.json](FEATURE_MATRIX.json).

| Stable feature ID | Behavior | Status | Source |
| --- | --- | --- | --- |
| `text.radio` | FM/DAB broadcast text and offline-first receivers | source_defined_not_hardware_verified | `textcenter/fm_rds.py` |
| `text.teletext` | DVB/Teletext source data and independent source labels | source_defined_not_hardware_verified | `textcenter/live_tv.py` |
| `text.web` | Responsive offline-first UI | source_defined_not_hardware_verified | `web/app.js` |

The JSON also captures must-not-change invariants, source/tests and suggested replaceable extension points. UI is intentionally customizable; behavioral equivalence still requires test evidence and owner approval before rollout. A Draft feature is not a shipped feature.
