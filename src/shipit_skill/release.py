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
import sys
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


def _tag_exists(tag: str) -> bool:
    try:
        r = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
                           capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


def _remote_tag_exists(tag: str) -> bool:
    try:
        r = subprocess.run(["git", "ls-remote", "--tags", "origin", tag],
                           capture_output=True, text=True)
        return tag in r.stdout
    except Exception:
        return False


def _changelog_entry(dir_: str, tag: str) -> str:
    """Extract the newest CHANGELOG.md entry for `tag` (or a generic body)."""
    ch = Path(dir_) / "CHANGELOG.md"
    if not ch.exists():
        return f"Release {tag}."
    lines = ch.read_text(encoding="utf-8").split("\n")
    start = -1
    end = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("## ") and start < 0:
            if tag.lstrip("v") in line or tag in line:
                start = i
        elif start >= 0 and line.startswith("## ") and i > start:
            end = i
            break
    if start < 0:
        return f"Release {tag}."
    body = "\n".join(line.rstrip() for line in lines[start + 1:end]).strip()
    return body or f"Release {tag}."


def execute(
    lang: str,
    pkg: str,
    how: str,
    repo: str | None = None,
    dir_: str = ".",
    title: str | None = None,
    server: str | None = None,
) -> None:
    """Actually run the release: doctor → bump → build → publish → tag → gh release → promo.

    The tag and GitHub Release are created only AFTER the registry publish
    succeeds. On publish failure it rolls back the commit and prints cleanup
    guidance. Re-running is safe: existing tags/releases are skipped.
    """
    from shipit_skill import doctor

    print("[0/7] doctor gate")
    checks = doctor.doctor()
    advisory = {
        "NPM_TOKEN set",
        "build module importable",
        "twine module importable",
        "node + npm available",
        "python version",
    }
    blocked = [c for c in checks if not c["ok"] and c["name"] not in advisory]
    if blocked:
        for c in blocked:
            print(f"  ✗ {c['name']}: {c['detail']}")
        print("\n❌ release blocked by doctor gaps (use `shipit-skill doctor` to inspect)")
        raise SystemExit(1)
    print("  ✓ all release checks pass")

    old = bump.parse_version(dir_)
    new = bump.bump(old, how) if not how.startswith("set:") else how[4:]
    tag = f"v{new}"

    print(f"[1/7] bump {old} → {new}")
    bump.set_version(dir_, new)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty",
                    "-m", f"chore: release {tag}"], check=True)

    print("[2/7] build")
    subprocess.run([sys.executable, "-m", "build"], check=True)

    print(f"[3/7] publish {pkg} to registry")
    try:
        if lang == "python":
            publish.execute_python(pkg, server)
        else:
            publish.execute_typescript(pkg)
    except Exception as e:
        print(f"\n❌ publish failed: {e}")
        print("Rolling back the 'chore: release' commit (nothing was pushed/tagged)…")
        subprocess.run(["git", "reset", "--soft", "HEAD~1"], check=True)
        print("✓ rolled back — version bump is staged. Next steps:")
        print("  fix the failure, then re-run the same release command")
        raise SystemExit(1)

    print(f"[4/7] tag {tag} + push")
    ch = Path(dir_) / "CHANGELOG.md"
    missing_entry = (not ch.exists()) or (
        f"## [{new}]" not in ch.read_text(encoding="utf-8")
    )
    if missing_entry:
        print(f"  ⚠ no CHANGELOG entry for [{new}] — notes will fall back to a generic body")
    if _tag_exists(tag) or _remote_tag_exists(tag):
        print(f"  {tag} already exists — skipping")
    else:
        subprocess.run(["git", "tag", tag], check=True)
    subprocess.run(["git", "push"], check=True)
    if not _remote_tag_exists(tag):
        subprocess.run(["git", "push", "origin", tag], check=True)

    if repo and _gh_available():
        exists = subprocess.run(["gh", "release", "view", tag, "--repo", repo],
                                capture_output=True).returncode == 0
        if exists:
            print(f"[5/7] GitHub Release {tag} already exists — skipping")
        else:
            print(f"[5/7] GitHub Release {tag}")
            release_title = title or f"{pkg} {tag}"
            notes = _changelog_entry(dir_, tag)
            body_path = Path(dir_) / ".release-notes.tmp"
            body_path.write_text(notes, encoding="utf-8")
            try:
                subprocess.run(
                    ["gh", "release", "create", tag, "--repo", repo, "--title", release_title,
                     "--notes-file", str(body_path)],
                    check=True,
                )
            finally:
                body_path.unlink(missing_ok=True)
    else:
        print("[5/7] (skip gh release — no --repo or gh CLI)")

    has_promo = (Path(dir_) / "promo").is_dir()
    if has_promo:
        print(f"[6/7] promo check ({new})")
        subprocess.run(
            [sys.executable, "-m", "shipit_skill.promo_check",
             "--dir", str(Path(dir_) / "promo"), "--version", new],
            check=True,
        )
    else:
        print("[6/7] (skip promo — no promo/ dir)")
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
