"""One-step release: bump → build → tag → GitHub Release → publish commands.

CLI:
    python -m shipit_skill.release --lang python [--pkg name] [--how patch|minor|major|set:X.Y.Z]
        [--repo owner/name] [--dir .] [--dry-run] [--title "..."]

Emits the gh tag/release and registry publish commands (publish needs a
user-supplied token). With --dry-run, only prints what would happen.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from shipit_skill import bump, publish


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip()


def _gh_available() -> bool:
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def release(
    lang: str,
    pkg: str,
    how: str,
    repo: str | None = None,
    dir_: str = ".",
    dry_run: bool = False,
    title: str | None = None,
    server: str | None = None,
) -> list[str]:
    """Return the list of shell commands for the release."""
    old = bump.parse_version(dir_)
    new = bump.bump(old, how) if not how.startswith("set:") else how[4:]

    cmds: list[str] = []
    cmds.append(f"# bump {old} → {new}")
    bump_cmd = f"python -m shipit_skill.bump {how} --dir {dir_}"
    cmds.append(bump_cmd + (" --dry-run" if dry_run else ""))
    if not dry_run:
        bump.set_version(dir_, new)

    cmds.append("python -m build")

    tag = f"v{new}"
    cmds.append(f"git add -A && git commit -m \"chore: release {tag}\"")
    cmds.append(f"git tag {tag} && git push && git push origin {tag}")

    if repo and _gh_available():
        release_title = title or f"{pkg} {tag}"
        cmds.append(
            f"gh release create {tag} --repo {repo} --title \"{release_title}\" "
            f"--generate-notes"
        )
    elif repo:
        cmds.append(f"# (gh CLI not found — create release manually at https://github.com/{repo}/releases/new)")

    # publish
    if lang == "python":
        if not dry_run:
            publish.print_python_commands(pkg, server, verify=True)
        cmds.append(f"# publish: run `shipit-skill publish --lang python --pkg {pkg} --verify`")
    else:
        publish.print_typescript_commands()

    has_promo = (Path(dir_) / "promo").is_dir()
    if has_promo:
        cmds.append(f"shipit-skill check-promo --dir {dir_}/promo --version {new}")
    else:
        cmds.append("# no promo/ — add one for Phase 4")
    return cmds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["python", "typescript"])
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--how", default="patch", help="patch|minor|major|set:X.Y.Z")
    ap.add_argument("--repo", help="owner/name for GitHub Release")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--server", help="MCP server name (python, for --verify)")
    ap.add_argument("--title")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for cmd in release(
        args.lang, args.pkg, args.how, args.repo, args.dir, args.dry_run, args.title, args.server
    ):
        print(cmd)
    print("\n# Commands above are guidance — review before running.")


if __name__ == "__main__":
    main()
