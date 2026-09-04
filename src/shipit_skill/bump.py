"""Semantic version bump + multi-file sync.

CLI:
    python -m shipit_skill.bump patch|minor|major|set:X.Y.Z [--dir .] [--dry-run]

Updates: pyproject.toml version, package __version__, CHANGELOG.md (prepends
an entry). Use --dry-run to preview without writing.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast


def parse(v: str) -> tuple[int, int, int]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", v)
    if not m:
        raise ValueError(f"invalid semver: {v!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump(current: str, how: str) -> str:
    major, minor, patch = parse(current)
    if how == "major":
        return f"{major + 1}.0.0"
    if how == "minor":
        return f"{major}.{minor + 1}.0"
    if how == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"unknown bump: {how}")


def set_version(dir_: str, new: str, dry_run: bool = False) -> list[str]:
    d = Path(dir_)
    old = parse_version(dir_)
    changes: list[str] = []

    py = d / "pyproject.toml"
    if py.exists():
        text = py.read_text(encoding="utf-8")
        updated = re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{new}"', text, count=1, flags=re.M)
        if updated != text:
            if not dry_run:
                py.write_text(updated, encoding="utf-8")
            changes.append(f"pyproject.toml: {old} → {new}")

    for init in (d / "src" / "shipit_skill" / "__init__.py", d / "shipit_skill" / "__init__.py"):
        if init.exists():
            text = init.read_text(encoding="utf-8")
            updated = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new}"', text, count=1)
            if updated != text:
                if not dry_run:
                    init.write_text(updated, encoding="utf-8")
                changes.append(f"{init.name}: {old} → {new}")

    ch = d / "CHANGELOG.md"
    if ch.exists():
        text = ch.read_text(encoding="utf-8")
        if f"## [{new}]" not in text:
            entry = f"## [{new}] - {date.today().isoformat()}\n\nBumped from {old}.\n\n"
            updated = re.sub(r"(?m)^# Changelog\n\n", f"# Changelog\n\n{entry}", text, count=1)
            if updated != text and not dry_run:
                ch.write_text(updated, encoding="utf-8")
            changes.append(f"CHANGELOG.md: added [{new}]")

    return changes


def parse_version(dir_: str) -> str:
    d = Path(dir_)
    py = d / "pyproject.toml"
    if py.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', py.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return "0.0.0"


def _utf8_stdout() -> None:
    try:
        cast(Any, sys.stdout).reconfigure(encoding="utf-8")
        cast(Any, sys.stderr).reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("how", help="patch | minor | major | set:X.Y.Z")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--commit", action="store_true", help="git add + commit the bump")
    args = ap.parse_args()

    old = parse_version(args.dir)
    new = bump(old, args.how) if not args.how.startswith("set:") else args.how[4:]

    changes = set_version(args.dir, new, dry_run=args.dry_run)
    for c in changes:
        print(("(dry) " if args.dry_run else "") + c)
    if not changes:
        print(f"no changes needed (already at {new})")
    print(f"\n{old} → {new}")

    if args.commit and not args.dry_run and changes:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"chore: bump version to {new}"],
            check=True,
        )
        print(f"committed: bump version to {new}")


if __name__ == "__main__":
    main()
