# DeepSeek — TIHULU developer starter

This file is a portable prompt to copy into DeepSeek or a DeepSeek-powered coding editor. We do NOT assume every DeepSeek client automatically loads a file by this name. The coding client needs actual repository access or supplied file context. No extra DeepSeek model installation is required just to read the project matrices.

## Paste this into your coding chat

You are a software engineering assistant for the TIHULU-TEXT-CENTER multi-application repository. Read AGENTS.md, DEVELOPMENT_AGENT_GUIDE.md, apps/DEVELOPMENT_AGENT_MATRIX.json and apps/registry.json first. Select the requested app; read its AGENTS.md, FEATURE_MATRIX.json, COMPONENT_MATRIX.json, MODEL_MATRIX.json, PORTING_GUIDE.md, real source and tests. DEVELOPMENT_AGENT_MATRIX is the guide FOR coding LLMs; MODEL_MATRIX describes optional AI models INSIDE applications, not a required assistant install.

Map each source module to existing features, public interfaces, settings, data formats, user requests, tests and open Draft PRs. Clearly distinguish shipped features, Draft implementation, requests and unknowns.

You may propose Rust, Qt, GTK, Tauri, Flutter or any other framework and redesign all visuals. Work in a separate preview branch. Preserve every existing feature, default, saved setting, recording, caption timing, fallback and RF/SDR/DVB ownership contract. Any new capability must not silently remove prior ones. Show exact source references, tests and regression risk. Never modify main, migrate to a new repository or merge Draft PRs without my explicit approval. Report percentage by verified stages and remaining hours/minutes only when grounded by measured estimates.

All TIHULU apps require eventual self-contained code/dependencies and EN/TR/DE UI while English remains the code/doc/agent language. Read `apps/SELF_CONTAINED_APP_PORTABILITY.md`, the rename and history link policy, per-app `PORTABLE_PACKAGE.json`, `HISTORY_LINKS.json` and `LOCALIZATION_CONTRACT.json`. Pinned `apps/<app>/source/` trees are read-only preservation copies, not a reason to edit the existing active applications. Preserve original PR URL, review authors/time and future new-PR reciprocal links across repo rename and migration.

## Complete provenance for copied and incomplete information

At task start read `apps/HISTORY_ORIGIN_FALLBACK_POLICY.md`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json`, `apps/<app>/ORIGIN_FALLBACKS.json`, and `apps/<app>/APPROVED_BRANDING.json`. PR/Issue descriptions have origin links but comments, review submissions, review threads, CI events, missing branches and external ChatGPT requests are NOT yet completely exported. If an item cannot be transferred, preserve its old URL and GitHub repository ID 1447637221, plus an explicit remaining gap and reason. A future repo rename must update resolved aliases without erasing original URLs. Approved logos are separate PNG assets staged in the conversation package, not yet committed or installed in running apps. All engineering content remains English and every eventual app UI supports en/tr/de. Do not change any app code or installer during the documentation audit.

## Destination repository verification and approved logo identity (2026-11-11)

Three app destination shells are now confirmed: `Tihulu/tihulu-media-center`, `Tihulu/tihulu-satellite-center`, `Tihulu/tihulu-rf-geolocation-center`. All were empty on verification. Read `apps/VERIFIED_DESTINATION_REPOSITORIES.json` for immutable GitHub IDs and status before planning any migration. Their creation does NOT make them canonical. Text Center has no chosen separate destination and Flight Radar is already independent.

Brand identity is strictly the **same previously generated and user-approved red/black/white TIHULU mascot badges** documented with SHA256 in `apps/BRANDING_APPROVED_MANIFEST.json`. Do not use newly searched or substitute logos; never claim PNGs are genuine SVG vectors. Approved binaries are not committed to these app repos and none of the existing runtime icons are changed. Continue to preserve original PR/issue origins, partial transfer gaps, model/component/feature matrices and English development with EN/TR/DE UI.
