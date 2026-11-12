"""Explicit offline packaging commands. There is intentionally NO install verb."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import (
    PackageError, build_to, compatibility_report, plan_install,
    review_rollback, verify_path,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rf_geolocation_center.packaging",
        description="RFGeo source package preparation. No OS/device installation or service changes.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("build", help="build reproducible portable tarball in existing directory")
    build.add_argument("--out-dir", type=Path, required=True)
    verify = sub.add_parser("verify", help="validate archive structure and all per-file SHA256")
    verify.add_argument("--archive", type=Path, required=True)
    plan = sub.add_parser("plan", help="print install dry-run and rollback ownership manifest")
    plan.add_argument("--archive", type=Path, required=True)
    plan.add_argument("--prefix", type=Path, required=True)
    plan.add_argument("--home", type=Path, required=True)
    rollback = sub.add_parser("rollback-review", help="inspect unchanged owned files; never delete")
    rollback.add_argument("--plan-json", type=Path, required=True)
    rollback.add_argument("--prefix", type=Path, required=True)
    sub.add_parser("check", help="read-only OS/Python compatibility assessment; no hardware probing")
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            result = build_to(Path(__file__).resolve().parents[1], args.out_dir)
        elif args.action == "verify":
            result = verify_path(args.archive)
        elif args.action == "plan":
            result = plan_install(args.archive, args.prefix, args.home, os.environ)
        elif args.action == "rollback-review":
            if args.plan_json.is_symlink():
                raise PackageError("refusing symlinked rollback plan")
            result = review_rollback(
                json.loads(args.plan_json.read_text(encoding="utf-8")), args.prefix,
            )
        elif args.action == "check":
            result = compatibility_report()
        else:
            raise PackageError("unsupported action")
    except (PackageError, OSError, ValueError, json.JSONDecodeError) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
