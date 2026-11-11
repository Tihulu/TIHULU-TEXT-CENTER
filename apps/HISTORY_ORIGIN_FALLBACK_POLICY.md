# Historical source fallback and GitHub rename-resistant traceability

**Scope:** every embedded TIHULU app plus externally canonical Flight Radar. Do not claim full PR/history migration from URL preservation alone.

## Required behavior for anything NOT fully transferred
Every file group, feature requirement, source decision, code review, issue, PR, branch, original source hash and partially transferred item must have a machine-readable **origin pointer** in the destination. Preserve the pointer even when the content was successfully copied.

Each pointer must include: `source_repository_id`, `source_original_full_name`, `original_url`, `source_ref` and `source_commit_sha` when verified, `original_object_id`/`number` when applicable, `original_author` and timestamp when known, `archive_path` and checksum for copied evidence, `coverage_status`, `reason_missing`, `last_verified_at`, and `destination_url` if a new object exists. If unknown, write `null` and an explicit `unknown` status — never fabricate the origin.

Use the already-preserved full legacy source URL as a historic record. **Never rewrite original links** after a repo rename. To find the current URL, look up GitHub repository numeric ID `1447637221` with permission, record the returned current name as an alias and validate the new source URL / redirect. A redirect is not a backup. Also keep copied source text, PR export JSON and Git bundles to survive deleted or inaccessible source where authorization and licenses permit.

## Origin coverage state machine
- `verified_copied`: bytes/data and original author/time/source checksum verified in archive
- `linked_only`: original GitHub URL and ID stored; body/comment not exported
- `partially_copied`: some content stored, missing categories listed with link
- `not_exported_or_unverified`: audit not yet performed, NOT proof records are unavailable
- `permission_denied`: tried, blocked, original ID/URL retained
- `deleted_or_unavailable`: checked and no longer retrievable, original ID/URL and last known evidence retained
- `native_object_not_portable`: GitHub original PR number, comment ID, approval status or timestamps cannot be recreated by ordinary PR API; export history as evidence and link new PR
- `fully_verified_and_crosslinked`: original and new links, snapshots, checksums, author/date and verification recorded

## Mandatory files after app repo cutover
Each new repo has:
- `ORIGIN.md` prominently naming the former app source and original source repo numeric ID
- `migration/origin.json` with source/destination code tree SHA and history graph map
- `history/ORIGIN_LINK_MAP.json` with the relevant per-app item-by-item original/new URLs
- `history/TRANSFER_GAPS.json` enumerating **everything not copied or not natively movable**, with reasons, source pointers and pending actions
- `history/PR_MAP.json` with old PR number/URL, new PR number/URL, original authors/reviews/comments as explicit historical records
- `history/requirements.jsonl` with user-provided chat requirements and verifiable origin pointers, or explicit missing-source status
- `AGENTS.md`, `CLAUDE.md` and `DEVELOPMENT_AGENT_GUIDE.md`: first action is to read origin map and transfer gaps, including old archive references

**No orphaned requirement:** if a user request, old PR, design decision or failed transfer is identified, it must be either verified in the new repo or present in a gap ledger with original link and a restoration task. This is a cutover gate, not a claim currently satisfied.

## Safety requirements
Original GitHub PRs and issues are left untouched; do not recreate approvals by impersonating original reviewers. Keep `HISTORY_COVERAGE_AUDIT.json` up to date and audit all API pages and threads. External ChatGPT conversations and inaccessible or private records require consent and authorized exports; do not scrape unseen chats or claim missing links exist.

Only relocate when source availability, fallback integrity, verified permissions, traceability and application behavior/regression gates pass; no app build or installer path changes in this documentation PR.
