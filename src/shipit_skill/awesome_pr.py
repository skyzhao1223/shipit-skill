"""Helper for submitting to awesome lists (e.g. awesome-mcp-servers).

CLI:
    python -m shipit_skill.awesome_pr --upstream punkpeye/awesome-mcp-servers \\
        --repo skyzhao1223/zspace-cli --fork skyzhao1223/awesome-mcp-servers \\
        --branch add-zspace-cli --title "Add skyzhao1223/zspace-cli to File Systems"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path


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


def _run(cmd: list[str], cwd: str | None = None) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        raise SystemExit(f"$ {' '.join(cmd)}\n  failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def _heading_index(text: str, category: str) -> int:
    """Index of the first markdown heading whose text contains `category`."""
    for i, line in enumerate(text.split("\n")):
        if re.match(r"^#{1,3}\s+", line) and category.lower() in line.lower():
            return i
    return -1


def execute(
    upstream: str,
    repo: str,
    fork: str,
    branch: str,
    category: str,
    description: str,
    install: str,
    title: str,
) -> str:
    """Actually open an awesome-list PR: fork → clone → branch → edit → push → gh pr create.

    Requires the `gh` CLI (authenticated) and network access.
    """
    head = fork.split("/")[0]
    pr_title = f"{title} 🤖🤖🤖" if title else f"Add {repo} to {category}"
    badge = (
        f"      [![{repo} MCP server]"
        f"(https://glama.ai/mcp/servers/{repo}/badges/score.svg)]"
        f"(https://glama.ai/mcp/servers/{repo}) \\"
    )
    entry = (
        f"    - [{repo}](https://github.com/{repo}) \\\n{badge}\n"
        f"      🐍 🏠 🍎 - {description} `{install}`"
    )

    print("[1/5] ensure fork")
    _run(["gh", "repo", "fork", upstream, "--clone=false"])
    print(f"      fork: {fork}")

    print(f"[2/5] clone {upstream} shallow")
    tmp = tempfile.mkdtemp(prefix="awesome-pr-")
    _run(["git", "clone", "--depth", "1", f"https://github.com/{upstream}.git", tmp])
    _run(["git", "checkout", "-q", "-b", branch], cwd=tmp)
    print(f"      branch: {branch}")

    print(f"[3/5] edit README (after '## {category}')")
    readme = Path(tmp) / "README.md"
    text = readme.read_text(encoding="utf-8")
    idx = _heading_index(text, category)
    if idx < 0:
        raise SystemExit(f"category heading containing {category!r} not found in README.md")
    lines = text.split("\n")
    insert_at = idx + 1
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    lines.insert(insert_at, entry)
    readme.write_text("\n".join(lines), encoding="utf-8")
    print(f"      inserted entry after line {idx + 1}")

    print("[4/5] push branch")
    _run(["git", "add", "README.md"], cwd=tmp)
    _run(["git", "commit", "-q", "-m", f"Add {repo} to {category}"], cwd=tmp)
    _run(["git", "push", "-f", "-u", f"https://github.com/{fork}.git", branch], cwd=tmp)

    print("[5/5] open PR")
    url = _run(
        ["gh", "pr", "create", "--repo", upstream, "--head", f"{head}:{branch}",
         "--title", pr_title, "--body", f"Adds {repo} to {category}.\n\n`{install}`"]
    )
    print(f"PR created: {url}")
    return url


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, help="punkpeye/awesome-mcp-servers")
    ap.add_argument("--repo", required=True, help="your server repo, e.g. skyzhao1223/zspace-cli")
    ap.add_argument("--fork", required=True, help="your fork of upstream")
    ap.add_argument("--branch", required=True, help="branch to create, e.g. add-zspace-cli")
    ap.add_argument("--title", default="", help="PR title; add ' 🤖🤖🤖' to opt into agent fast-track")  # noqa: E501
    ap.add_argument("--category", help="heading to insert under (with --execute)")
    ap.add_argument("--description", help="one-line description (with --execute)")
    ap.add_argument("--install", help="install command, e.g. npx foo (with --execute)")
    ap.add_argument("--execute", action="store_true", help="actually open the PR via gh")
    args = ap.parse_args()

    if args.execute:
        if not (args.category and args.description and args.install):
            ap.error("--execute requires --category, --description and --install")
        execute(args.upstream, args.repo, args.fork, args.branch, args.category,
                args.description, args.install, args.title)
        return

    print(recipe(args.upstream, args.repo, args.fork, args.branch, args.title))
    print("# Commands above are guidance; nothing was executed.")


if __name__ == "__main__":
    main()
