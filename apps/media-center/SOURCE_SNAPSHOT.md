# TIHULU Media Center — portable source snapshot and future standalone application

Read-only source copies are available in `apps/media-center/source/` at the original Git tree hashes below. They are **not** active implementation paths and do **not** make a fully independent binary/installer. Source trees were copied without editing application files.

| Copied source folder | Exact original Git tree SHA | Role |
| --- | --- | --- |
| `source/kaffeine_next/` | `4be76ef898a4adcc779c96052341fffdef0658a3` | application_source |
| `source/tv_center/` | `73aa1e74465f48d33103424b4a1072d93c57d1cc` | application_source_and_shared_workers |
| `source/textcenter/` | `dfc5fefbedba31f133f5a9ee34667961f3c3ef14` | copied_shared_code_dependency |


The snapshot baseline is `9b4ffce98a723c0e60ec5a11978895e56f97a161`. Newer Draft PR branches may contain additional features not yet present in this snapshot. Reconcile branch histories before any release or cutover.

See `PORTABLE_PACKAGE.json` for incomplete external/upstream dependency closure, `HISTORY_LINKS.json` for PR/issue provenance and pending future bi-directional links, `LOCALIZATION_CONTRACT.json` for required EN/TR/DE UI, and `FEATURE_MATRIX.json`, `COMPONENT_MATRIX.json`, `MODEL_MATRIX.json` for architecture. The optional in-app AI models are not required for coding-agent documentation.

**All development instructions and internal engineering language are English.** UI translations will be added and verified separately without altering existing production defaults in this PR. No application has been moved to a new repository.
