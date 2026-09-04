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


def execute(
    lang: str,
    pkg: str,
    how: str,
    repo: str | None = None,
    dir_: str = ".",
    title: str | None = None,
    server: str | None = None,
) -> None:
    """Actually run the release: bump → build → publish → tag → gh release → promo.

    The tag and GitHub Release are created only AFTER the registry publish
    succeeds, so a failed upload never leaves a dangling release. On failure
    it rolls back the tag and prints cleanup guidance.
    """
    old = bump.parse_version(dir_)
    new = bump.bump(old, how) if not how.startswith("set:") else how[4:]
    tag = f"v{new}"

    print(f"[1/6] bump {old} → {new}")
    bump.set_version(dir_, new)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"chore: release {tag}"], check=True)

    print("[2/6] build")
    subprocess.run(["python3", "-m", "build"], check=True)

    print(f"[3/6] publish {pkg} to registry")
    try:
        if lang == "python":
            publish.execute_python(pkg, server)
        else:
            publish.execute_typescript()
    except Exception as e:
        print(f"\n❌ publish failed: {e}")
        print("Rolling back the 'chore: release' commit (nothing was pushed/tagged)…")
        subprocess.run(["git", "reset", "--soft", "HEAD~1"], check=True)
        print("✓ rolled back — version bump is staged. Next steps:")
        print("  fix the failure, then re-run the same release command")
        raise SystemExit(1)

    print(f"[4/6] tag {tag} + push")
    subprocess.run(["git", "tag", tag], check=True)
    subprocess.run(["git", "push"], check=True)
    subprocess.run(["git", "push", "origin", tag], check=True)

    if repo and _gh_available():
        print(f"[5/6] GitHub Release {tag}")
        release_title = title or f"{pkg} {tag}"
        subprocess.run(
            ["gh", "release", "create", tag, "--repo", repo, "--title", release_title,
             "--generate-notes"],
            check=True,
        )
    else:
        print("[5/6] (skip gh release — no --repo or gh CLI)")

    has_promo = (Path(dir_) / "promo").is_dir()
    if has_promo:
        print(f"[6/6] promo check ({new})")
        subprocess.run(
            ["python3", "-m", "shipit_skill.promo_check",
             "--dir", str(Path(dir_) / "promo"), "--version", new],
            check=True,
        )
    else:
        print("[6/6] (skip promo — no promo/ dir)")
    print(f"\nReleased {tag} ✅")


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
    ap.add_argument("--execute", action="store_true", help="actually run the release")
    args = ap.parse_args()

    if args.execute:
        execute(args.lang, args.pkg, args.how, args.repo, args.dir, args.title, args.server)
        return

    for cmd in release(
        args.lang, args.pkg, args.how, args.repo, args.dir, args.dry_run, args.title, args.server
    ):
        print(cmd)
    print("\n# Commands above are guidance — review before running.")


if __name__ == "__main__":
    main()
