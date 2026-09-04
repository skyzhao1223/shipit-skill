"""Promo freshness check — stale versions, unknown PRs, broken links.

CLI:
    python -m shipit_skill.promo_check --dir promo --version 0.1.1
    python -m shipit_skill.promo_check --dir promo --version 0.1.1 --prs 8262=closed,13600=open

Exit code 1 if any stale version, unknown PR, or broken link is found.
"""

from __future__ import annotations

import argparse
import re
import urllib.request
from pathlib import Path

# Match "v0.1.0" / "0.1.1" but NOT "127.0.0.1" (IPs).
SEMVER = re.compile(r"(?<![\d.])(?:v)?0\.\d+\.\d+\b")
PR_LINK = re.compile(r"#(\d{4,})")
RELEASE_URL = re.compile(r"releases/tag/([\w.]+)")
GITHUB_URL = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+")


def _url_ok(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status < 400
    except Exception:
        return False


def check_dir(
    directory: str,
    version: str,
    prs: dict[str, str] | None = None,
    check_links: bool = True,
) -> list[str]:
    """Return a list of issues. Empty list means OK."""
    known_prs = prs or {}
    target = tuple(int(x) for x in version.split("."))
    errors: list[str] = []

    for path in sorted(Path(directory).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for m in SEMVER.finditer(text):
            v = m.group(0).lstrip("v")
            cur = tuple(int(x) for x in v.split("."))
            if cur != target:
                line = text[: m.start()].count("\n") + 1
                errors.append(f"{path.name}:{line}: stale version {v} (current {version})")
        for m in PR_LINK.finditer(text):
            pid = m.group(1)
            if pid not in known_prs:
                line = text[: m.start()].count("\n") + 1
                errors.append(
                    f"{path.name}:{line}: unknown PR/issue #{pid} (known: {sorted(known_prs)})"
                )
        for m in RELEASE_URL.finditer(text):
            tag = m.group(1)
            line = text[: m.start()].count("\n") + 1
            print(f"{path.name}:{line}: release tag {tag} (verify manually)")
        if check_links:
            for m in GITHUB_URL.finditer(text):
                url = m.group(0)
                line = text[: m.start()].count("\n") + 1
                if not _url_ok(url):
                    errors.append(f"{path.name}:{line}: broken link {url}")

    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--version", required=True, help="current version, e.g. 0.1.1")
    ap.add_argument("--prs", default="", help="known PRs as id=state,... e.g. 13600=open")
    ap.add_argument("--no-links", action="store_true", help="skip HTTP link checks")
    ap.add_argument("--report", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    known_prs = {k: v for k, v in (kv.split("=") for kv in args.prs.split(",") if kv)}
    errors = check_dir(args.dir, args.version, prs=known_prs, check_links=not args.no_links)

    if args.report:
        import json

        by_file: dict[str, list[str]] = {}
        for e in errors:
            name = e.split(":", 1)[0]
            by_file.setdefault(name, []).append(e)
        print(json.dumps({
            "version": args.version,
            "dir": args.dir,
            "ok": not errors,
            "errors": errors,
            "by_file": by_file,
        }, indent=2))
        if errors:
            raise SystemExit(1)
        return

    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("OK: no stale versions, unknown PRs, or broken links.")


if __name__ == "__main__":
    main()
