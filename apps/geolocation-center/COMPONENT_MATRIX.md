# geolocation-center — source component → portable interface map

These are **proposed architecture mappings**, not a Rust port and not a promise that every feature is hardware-tested. Use any framework as long as original behavior is preserved.

| Present source | Responsibility | Portable interface | Example Rust destination |
| --- | --- | --- | --- |
| `rf_geolocation_center/core/positioning.mjs, rf_geolocation_center/core/evidence.mjs` | Observation-based location estimation and source evidence | `geo.position_solver` | `domain::location_estimator + domain::evidence` |
| `rf_geolocation_center/web/maps.mjs, rf_geolocation_center/web/simple_ui.mjs` | Geolocation map, layer and circles UI | `geo.map_view` | `ui::maps_and_layers` |
| `rf_geolocation_center/native.py, rf_geolocation_center/radio_metadata.py` | Native bridge and passive radio metadata provenance | `geo.source_adapter` | `adapters::nmea_gnss + adapters::radio_evidence` |
| `rf_geolocation_center/core/location_layers.mjs` | Geolocation layer selection | `geo.layers` | `domain::layer_graph` |

For exact behavioral constraints, tested/untested caveats, and non-Rust alternatives read [COMPONENT_MATRIX.json](COMPONENT_MATRIX.json), [FEATURE_MATRIX.json](FEATURE_MATRIX.json), [MODEL_MATRIX.json](MODEL_MATRIX.json), and `apps/PARITY_RELEASE_GATES.md`. Map current code changes onto new modules without forcing any UI theme or implementation language.
