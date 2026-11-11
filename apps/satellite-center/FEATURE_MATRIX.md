# satellite-center — behavior preservation matrix

Source of truth for mapping existing features across languages/frameworks: [FEATURE_MATRIX.json](FEATURE_MATRIX.json).

| Stable feature ID | Behavior | Status | Source |
| --- | --- | --- | --- |
| `satellite.planning` | Satellite orbital pass planning | source_defined_not_hardware_verified | `satellite_center/README.md` |
| `satellite.rf_capture` | Bounded on-demand IQ capture and ownership | source_defined_not_hardware_verified | `satellite_center/README.md` |
| `satellite.image_decode` | Robot36 and Meteor/ISS image flow | source_defined_not_hardware_verified | `satellite_center/compute_backends.py` |

The JSON also captures must-not-change invariants, source/tests and suggested replaceable extension points. UI is intentionally customizable; behavioral equivalence still requires test evidence and owner approval before rollout. A Draft feature is not a shipped feature.
