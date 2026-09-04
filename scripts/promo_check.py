#!/usr/bin/env python3
"""Check promo material freshness: versions, PR numbers, release URLs.

Usage:
    python3 scripts/promo_check.py --dir promo --version 0.1.1
    python3 scripts/promo_check.py --dir promo --version 0.1.1 --prs 8262=closed,13600=open

Scans *.md in --dir for:
  - version numbers (semver) that differ from --version (reports old ones)
  - GitHub PR/issue links (#NNNNN) not present in --prs
  - github release/tag URLs (reports for manual eyeball)
Exit code 1 if any stale version or unknown PR is found.
"""

import argparse
import re
import sys
from pathlib import Path

# Match "v0.1.0" / "0.1.1" / " 0.3.0" but NOT "127.0.0.1" (IPs) or "x.y.z".
SEMVER = re.compile(r"(?<![\d.])(?:v)?0\.\d+\.\d+\b")
PR_LINK = re.compile(r"#(\d{4,})")
RELEASE_URL = re.compile(r"releases/tag/([\w.]+)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--version", required=True, help="current version, e.g. 0.1.1")
    ap.add_argument("--prs", default="", help="known PRs as id=state,... e.g. 13600=open")
    args = ap.parse_args()

    known_prs = {k: v for k, v in (kv.split("=") for kv in args.prs.split(",") if kv)}
    target = tuple(int(x) for x in args.version.split("."))
    errors: list[str] = []

    for path in sorted(Path(args.dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for m in SEMVER.finditer(text):
            v = m.group(0).lstrip("v")
            cur = tuple(int(x) for x in v.split("."))
            if cur != target:
                line = text[: m.start()].count("\n") + 1
                errors.append(f"{path.name}:{line}: stale version {v} (current {args.version})")
        for m in PR_LINK.finditer(text):
            pid = m.group(1)
            if pid not in known_prs:
                line = text[: m.start()].count("\n") + 1
                errors.append(f"{path.name}:{line}: unknown PR/issue #{pid} (known: {sorted(known_prs)})")
        for m in RELEASE_URL.finditer(text):
            tag = m.group(1)
            line = text[: m.start()].count("\n") + 1
            print(f"{path.name}:{line}: release tag {tag} (verify manually)")

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("OK: no stale versions or unknown PRs.")


if __name__ == "__main__":
    main()
