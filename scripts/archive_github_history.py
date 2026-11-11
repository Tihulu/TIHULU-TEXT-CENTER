#!/usr/bin/env python3
"""Opt-in GitHub PR/issue comment, review and commit evidence snapshot.

Usage:
  GITHUB_TOKEN=... python3 scripts/archive_github_history.py \
    --repository Tihulu/TIHULU-TEXT-CENTER --all \
    --output apps/_archives/reviews

No network or mutation occurs without explicit CLI execution. Original IDs,
author handles and timestamps remain *historical evidence*, not approvals
or author attribution on recreated PRs. Never persist the authorization token.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"
PAGE_LIMIT = 500


def get_json(endpoint: str, token: str):
    request = Request(
        API + endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer " + token,
            "User-Agent": "tihulu-portable-history-archive",
        },
    )
    try:
        with urlopen(request, timeout=35) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("GitHub archive API request failed at " +
                           endpoint + ": " + str(exc)) from exc


def get_pages(endpoint: str, token: str):
    records = []
    for page in range(1, PAGE_LIMIT + 1):
        delimiter = "&" if "?" in endpoint else "?"
        url = endpoint + delimiter + "per_page=100&page=" + str(page)
        data = get_json(url, token)
        if not isinstance(data, list):
            raise ValueError("Expected list response: " + endpoint)
        records.extend(data)
        if len(data) < 100:
            return records
    raise ValueError("Pagination limit exceeded; no complete archive: " +
                     endpoint)


def evidence(record, kind):
    """Keep source object intact; original author/date is never rewritten."""
    return {"source_kind": kind, "source_url": record.get("html_url") or
            record.get("url"), "source_id": record.get("id"),
            "original_author": (record.get("user") or {}).get("login"),
            "original_created_at": record.get("created_at") or
            record.get("submitted_at"), "original_updated_at":
            record.get("updated_at"), "historical_not_new_approval": True,
            "github_record": record}


def pr_snapshot(repository: str, number: int, token: str):
    root = "/repos/" + repository
    pr = get_json(root + "/pulls/" + str(number), token)
    payload = {
        "schema_version": 1,
        "origin_repository": repository,
        "origin_pr_number": number,
        "origin_pr_url": pr.get("html_url"),
        "origin_head_sha": ((pr.get("head") or {}).get("sha")),
        "origin_base_sha": ((pr.get("base") or {}).get("sha")),
        "snapshot_created_utc": datetime.now(timezone.utc).isoformat(),
        "records": {},
        "completeness": {},
    }
    endpoints = {
        "issue_comments": root + "/issues/" + str(number) + "/comments",
        "review_comments": root + "/pulls/" + str(number) + "/comments",
        "reviews": root + "/pulls/" + str(number) + "/reviews",
        "timeline": root + "/issues/" + str(number) + "/timeline",
        "commits": root + "/pulls/" + str(number) + "/commits",
        "changed_files": root + "/pulls/" + str(number) + "/files",
    }
    for kind, endpoint in endpoints.items():
        result = get_pages(endpoint, token)
        payload["records"][kind] = [evidence(row, kind) for row in result]
        payload["completeness"][kind] = {
            "endpoint": endpoint, "count": len(result), "status": "complete",
        }
    # Entire original PR description and original GitHub metadata are
    # saved as evidence as well; commits use source SHA/parent references.
    payload["records"]["original_pr"] = evidence(pr, "pull_request")
    return payload


def archive(repository: str, numbers: list[int], destination: Path,
            token: str):
    destination.mkdir(parents=True, exist_ok=True)
    created = []
    for number in numbers:
        target = destination / ("pr-" + str(number).zfill(5) + ".json")
        if target.exists():
            raise FileExistsError("Refusing to overwrite " + str(target))
        item = pr_snapshot(repository, number, token)
        # X mode means reruns cannot silently replace an existing archive.
        with target.open("x", encoding="utf-8") as file:
            json.dump(item, file, ensure_ascii=False, indent=2)
            file.write("\n")
        created.append(target)
        print(str(target), file=sys.stderr)
    return created


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True,
                        help="OWNER/REPO, with no URL or paths")
    parser.add_argument("--output", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--all", action="store_true",
                      help="Archive every pull request, all states")
    mode.add_argument("--pr", action="append", type=int,
                      help="PR number, may be repeated")
    opts = parser.parse_args(args)
    from re import fullmatch
    if not fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", opts.repository):
        parser.error("Expected OWNER/REPO")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        parser.error("GITHUB_TOKEN is required to avoid unauthenticated "
                     "rate limits on complete PR history")
    repository = "/".join(quote(part, safe="") for part in
                          opts.repository.split("/"))
    if opts.all:
        prs = get_pages("/repos/" + repository +
                        "/pulls?state=all", token)
        numbers = sorted({int(item["number"]) for item in prs})
    else:
        numbers = sorted(set(opts.pr))
    if not numbers or any(n < 1 for n in numbers):
        parser.error("No valid PR number found")
    outputs = archive(repository, numbers, Path(opts.output), token)
    print(json.dumps({"status": "exported",
                      "records": len(outputs),
                      "paths": [str(p) for p in outputs]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
