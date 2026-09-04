#!/usr/bin/env python3
"""Check Glama listing status + badge availability for an MCP server.

Usage:
    python3 scripts/glama.py --repo skyzhao1223/zspace-cli [--poll 6] [--wait 40]

Prints page status and badge status. With --poll, retries N times waiting
--wait seconds between tries (Glama builds can take minutes to hours).
Exit 0 if page is live (200), else 1.
"""

import argparse
import time
import urllib.request


def status(url: str, ua: bool = True) -> int:
    req = urllib.request.Request(url)
    if ua:
        req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except Exception:
        return 404


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--poll", type=int, default=0, help="poll attempts")
    ap.add_argument("--wait", type=int, default=40, help="seconds between polls")
    args = ap.parse_args()

    page = f"https://glama.ai/mcp/servers/{args.repo}"
    badge = f"{page}/badges/score.svg"

    code = status(page)
    print(f"page : {code}  {page}")
    print(f"badge: {status(badge)}  {badge}")

    tries = 0
    while code != 200 and tries < args.poll:
        tries += 1
        print(f"waiting {args.wait}s (try {tries}/{args.poll})...")
        time.sleep(args.wait)
        code = status(page)
        print(f"page : {code}  {page}")
        if code == 200:
            print(f"badge: {status(badge)}  {badge}")

    if code != 200:
        print("NOT LISTED YET — check the Glama dashboard for build/check status.")
        raise SystemExit(1)
    print("LISTED ✅")


if __name__ == "__main__":
    main()
