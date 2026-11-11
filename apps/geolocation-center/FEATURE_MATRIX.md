# geolocation-center — behavior preservation matrix

Source of truth for mapping existing features across languages/frameworks: [FEATURE_MATRIX.json](FEATURE_MATRIX.json).

| Stable feature ID | Behavior | Status | Source |
| --- | --- | --- | --- |
| `geo.positioning` | GNSS / RF evidence positioning | source_defined_not_hardware_verified | `rf_geolocation_center/core/positioning.mjs` |
| `geo.hardware` | Read-only receiver discovery and integration boundaries | source_defined_not_hardware_verified | `rf_geolocation_center/docs/ARCHITECTURE_AND_RELEASE_GATES.md` |
| `geo.ui` | Circle/map and responsive design | source_defined_not_hardware_verified | `rf_geolocation_center/web/maps.mjs` |

The JSON also captures must-not-change invariants, source/tests and suggested replaceable extension points. UI is intentionally customizable; behavioral equivalence still requires test evidence and owner approval before rollout. A Draft feature is not a shipped feature.
