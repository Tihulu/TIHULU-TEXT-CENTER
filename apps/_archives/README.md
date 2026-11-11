# Source-preserving PR, issue and development record

Snapshot prepared on 2026-11-11 from GitHub PR and issue list endpoints for `Tihulu/TIHULU-TEXT-CENTER` and kept on a separate review-only branch. The snapshot contains **all visible 63 PR titles, bodies, source URLs, head/base refs and SHA metadata** in numbered JSON parts, plus available standalone issues. `pr-index.json` has routing candidates; these heuristic assignments are not final ownership decisions.

**Not yet exported at this stage:** complete review comments, approval timelines, inline discussions, issue event timelines, full Git commit diffs, conversations outside GitHub, or all historical LLM matrices. The originals remain the authoritative sources until verified snapshots are exported. A future migration must fetch `issues/{n}/comments`, `pulls/{n}/comments`, `pulls/{n}/reviews`, timeline events, PR commits and patch, plus all pages of each endpoint and audit counts; record errors and gaps.

Archives are evidence: never silently edit original text or rewrite original author/timestamps as if new comments. Re-migration should reference source URL and use `PR_MAP.json` to connect historical and fresh PRs. This does not replace an authenticated original GitHub repo.

## Supplemental cross-application portability PRs

After the first 63-PR snapshot, Draft PRs #68, #69, #70 and #71 were opened for portable archive, LLM matrices, coding agents and all-app independence. Their original descriptions and observed head/base SHAs are separately snapshotted in `portability-prs-68-71.json`, and all 67 original PR IDs/URLs are linked in `PORTABLE_HISTORY_LINK_MAP.json`. The initial `pr-index.json` and `pr-body-01..06.json` remain immutable baseline evidence. Neither the supplemental snapshot nor the link map contains complete review threads or external chats; no new PR is yet created in a destination repository. Snapshot head SHAs may become stale as branches advance. Preserve old URLs even after a future monorepo rename.
