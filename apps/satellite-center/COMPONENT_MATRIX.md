# satellite-center — source component → portable interface map

These are **proposed architecture mappings**, not a Rust port and not a promise that every feature is hardware-tested. Use any framework as long as original behavior is preserved.

| Present source | Responsibility | Portable interface | Example Rust destination |
| --- | --- | --- | --- |
| `satellite_center/browser/pass_window.mjs, satellite_center/browser/orbit_clock.mjs` | Orbital prediction and pass clock | `satellite.pass_planner` | `domain::orbits + domain::clock` |
| `satellite_center/bridge.py, satellite_center/browser/capture_duration.mjs` | Receive-only SDR capture bridge and segment limits | `satellite.rf_capture` | `adapters::sdr_capture` |
| `satellite_center/compute_backends.py, satellite_center/browser/compute_backends.mjs` | Image DSP compute readiness and backend selection | `satellite.compute_backend` | `domain::sstv_dsp + adapters::cuda` |
| `satellite_center/browser/index.html, satellite_center/browser/browser.js` | Earth/sky map, satellite lists and controls | `satellite.ui_shell` | `ui::satellite_dashboard` |

For exact behavioral constraints, tested/untested caveats, and non-Rust alternatives read [COMPONENT_MATRIX.json](COMPONENT_MATRIX.json), [FEATURE_MATRIX.json](FEATURE_MATRIX.json), [MODEL_MATRIX.json](MODEL_MATRIX.json), and `apps/PARITY_RELEASE_GATES.md`. Map current code changes onto new modules without forcing any UI theme or implementation language.
