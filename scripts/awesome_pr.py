#!/usr/bin/env python3
"""Helper for submitting to awesome lists (e.g. awesome-mcp-servers).

Automates the mechanical parts; keeps the human-verifiable steps explicit.

Usage:
    python3 scripts/awesome_pr.py --upstream punkpeye/awesome-mcp-servers \
        --repo skyzhao1223/zspace-cli --fork skyzhao1223/awesome-mcp-servers \
        --branch add-zspace-cli --title "Add skyzhao1223/zspace-cli to File Systems"

Steps printed (fork sync, branch, edit README, push, create PR). The README
edit itself is intentionally manual — every list has its own format.
"""

# ruff: noqa: E501
import argparse
import subprocess
import sys


def sh(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
    return r.stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, help="punkpeye/awesome-mcp-servers")
    ap.add_argument("--repo", required=True, help="your server repo, e.g. skyzhao1223/zspace-cli")
    ap.add_argument("--fork", required=True, help="your fork of upstream")
    ap.add_argument("--branch", required=True, help="branch to create, e.g. add-zspace-cli")
    ap.add_argument("--title", default="", help="PR title; add ' 🤖🤖🤖' to opt into agent fast-track")
    args = ap.parse_args()

    print(f"""# awesome PR recipe — {args.repo}

## 0. Prereqs
- Glama listing live (run `python3 scripts/glama.py --repo {args.repo}`) — most
  maintainers now REQUIRE the Glama score badge in the entry. Submit Glama first.

## 1. Sync fork main
    gh api repos/{args.fork}/merge-upstream -X POST -f branch=main

## 2. Branch off latest upstream (in a fresh shallow clone)
    cd /tmp && rm -rf ams
    git clone --depth 1 https://github.com/{args.fork}.git ams && cd ams
    git checkout -q -b {args.branch}
    # if {args.branch} already exists from a closed PR: force push at the end

## 3. Edit README
    # find your category anchor, add the entry after it. Format (typical):
    - [{args.repo}](https://github.com/{args.repo}) \\
      [![{args.repo} MCP server](https://glama.ai/mcp/servers/{args.repo}/badges/score.svg)](https://glama.ai/mcp/servers/{args.repo}) \\
      🐍 🏠 🍎 - <one-line description> \\`<install cmd>\\`

## 4. Push + PR
    git add README.md
    git commit -m "Add {args.repo} to <Category>"
    git push -f -u origin {args.branch}     # -f only if branch existed before
    gh pr create --repo {args.upstream} --head {args.fork.split('/')[0]}:{args.branch} \\
      --title "{args.title} 🤖🤖🤖" --body "<markdown body>"
""")

    print("# Commands above are guidance; nothing was executed.")


if __name__ == "__main__":
    main()
