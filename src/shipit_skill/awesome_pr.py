"""Helper for submitting to awesome lists (e.g. awesome-mcp-servers).

CLI:
    python -m shipit_skill.awesome_pr --upstream punkpeye/awesome-mcp-servers \\
        --repo skyzhao1223/zspace-cli --fork skyzhao1223/awesome-mcp-servers \\
        --branch add-zspace-cli --title "Add skyzhao1223/zspace-cli to File Systems"
"""

from __future__ import annotations

import argparse


def recipe(
    upstream: str,
    repo: str,
    fork: str,
    branch: str,
    title: str = "",
) -> str:
    """Return the awesome-list submission recipe as text (no side effects)."""
    head = fork.split("/")[0]
    title_cmd = f"{title} 🤖🤖🤖" if title else "<markdown title>"
    badge = (
        f"      [![{repo} MCP server]"
        f"(https://glama.ai/mcp/servers/{repo}/badges/score.svg)]"
        f"(https://glama.ai/mcp/servers/{repo}) \\"
    )
    lines = [
        f"# awesome PR recipe — {repo}",
        "",
        "## 0. Prereqs",
        f"- Glama listing live (run `shipit-skill check-glama --repo {repo}`) — most",
        "  maintainers now REQUIRE the Glama score badge in the entry.",
        "  Submit Glama first.",
        "",
        "## 1. Sync fork main",
        f"    gh api repos/{fork}/merge-upstream -X POST -f branch=main",
        "",
        "## 2. Branch off latest upstream (in a fresh shallow clone)",
        "    cd /tmp && rm -rf ams",
        f"    git clone --depth 1 https://github.com/{fork}.git ams && cd ams",
        f"    git checkout -q -b {branch}",
        f"    # if {branch} already exists from a closed PR: force push at the end",
        "",
        "## 3. Edit README",
        "    # find your category anchor, add the entry after it. Format (typical):",
        f"    - [{repo}](https://github.com/{repo}) \\",
        badge,
        "      🐍 🏠 🍎 - <one-line description> `<install cmd>`",
        "",
        "## 4. Push + PR",
        "    git add README.md",
        f"    git commit -m \"Add {repo} to <Category>\"",
        f"    git push -f -u origin {branch}     # -f only if branch existed before",
        f"    gh pr create --repo {upstream} --head {head}:{branch} \\",
        f'      --title "{title_cmd}" --body "<markdown body>"',
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, help="punkpeye/awesome-mcp-servers")
    ap.add_argument("--repo", required=True, help="your server repo, e.g. skyzhao1223/zspace-cli")
    ap.add_argument("--fork", required=True, help="your fork of upstream")
    ap.add_argument("--branch", required=True, help="branch to create, e.g. add-zspace-cli")
    ap.add_argument("--title", default="", help="PR title; add ' 🤖🤖🤖' to opt into agent fast-track")  # noqa: E501
    args = ap.parse_args()

    print(recipe(args.upstream, args.repo, args.fork, args.branch, args.title))
    print("# Commands above are guidance; nothing was executed.")


if __name__ == "__main__":
    main()
