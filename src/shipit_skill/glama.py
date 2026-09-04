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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--poll", type=int, default=0, help="poll attempts")
    ap.add_argument("--wait", type=int, default=40, help="seconds between polls")
    args = ap.parse_args()

    if not check_glama(args.repo, poll=args.poll, wait=args.wait):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
