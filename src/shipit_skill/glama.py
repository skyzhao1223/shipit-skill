"""Glama listing status + badge availability check.

CLI:
    python -m shipit_skill.glama --repo skyzhao1223/zspace-cli [--poll 6] [--wait 40]
"""

from __future__ import annotations

import argparse
import time
import urllib.request


def fetch_status(url: str) -> int:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except Exception:
        return 404


def check_glama(repo: str, poll: int = 0, wait: int = 40) -> bool:
    """Return True when the server page is live (200). Polls if requested."""
    page = f"https://glama.ai/mcp/servers/{repo}"
    badge = f"{page}/badges/score.svg"

    code = fetch_status(page)
    print(f"page : {code}  {page}")
    print(f"badge: {fetch_status(badge)}  {badge}")

    tries = 0
    while code != 200 and tries < poll:
        tries += 1
        print(f"waiting {wait}s (try {tries}/{poll})...")
        time.sleep(wait)
        code = fetch_status(page)
        print(f"page : {code}  {page}")
        if code == 200:
            print(f"badge: {fetch_status(badge)}  {badge}")

    if code != 200:
        print("NOT LISTED YET — check the Glama dashboard for build/check status.")
        return False
    print("LISTED ✅")
    return True


def add_badge(repo: str, readme: str = "README.md") -> bool:
    """Insert the Glama score badge after the README title (idempotent)."""
    badge = (
        f"[![{repo} MCP server]"
        f"(https://glama.ai/mcp/servers/{repo}/badges/score.svg)]"
        f"(https://glama.ai/mcp/servers/{repo})"
    )
    from pathlib import Path

    path = Path(readme)
    if not path.exists():
        print(f"README not found: {readme}")
        return False
    text = path.read_text(encoding="utf-8")
    if badge.split("]")[0] in text:
        print("badge already present")
        return True
    # insert after the first "# Title" line
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(i + 1, "", )
            lines.insert(i + 1, badge)
            break
    else:
        lines.insert(0, badge)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"badge added to {readme}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--poll", type=int, default=0, help="poll attempts")
    ap.add_argument("--wait", type=int, default=40, help="seconds between polls")
    ap.add_argument("--add-badge", action="store_true", help="write badge to README when listed")
    ap.add_argument("--readme", default="README.md", help="README path (with --add-badge)")
    args = ap.parse_args()

    if not check_glama(args.repo, poll=args.poll, wait=args.wait):
        raise SystemExit(1)
    if args.add_badge:
        if not add_badge(args.repo, args.readme):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
