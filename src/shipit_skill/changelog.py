"""Changelog generator — build a CHANGELOG entry from git log.

CLI:
    python -m shipit_skill.changelog --from v0.6.0 --version 0.7.0
    python -m shipit_skill.changelog --version 0.7.0          # from last tag
    python -m shipit_skill.changelog --version 0.7.0 --write  # prepend to CHANGELOG.md

Categorizes conventional commits (feat/fix/docs/...) into sections and emits
markdown that `release --execute` can use as release notes.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

SECTIONS: list[tuple[str, list[str]]] = [
    ("Features", ["feat"]),
    ("Fixes", ["fix"]),
    ("Docs", ["docs", "doc"]),
    ("Chores", ["chore", "refactor", "test", "ci", "build", "perf", "style"]),
]

COMMIT = re.compile(
    r"^(feat|fix|docs?|chore|refactor|test|ci|build|perf|style)"
    r"(?:\(.+?\))?!?:\s+(.+)$"
)


def _utf8_stdout() -> None:
    try:
        cast(Any, sys.stdout).reconfigure(encoding="utf-8")
        cast(Any, sys.stderr).reconfigure(encoding="utf-8")
    except Exception:
        pass


def last_tag() -> str | None:
    r = subprocess.run(["git", "describe", "--tags", "--abbrev=0"],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def _git_log(from_ref: str | None) -> list[str]:
    args = ["git", "log", "--pretty=format:%s"]
    if from_ref:
        args += [f"{from_ref}..HEAD"]
    else:
        args += ["-n", "50"]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git log failed: {r.stderr.strip()}")
    return [line for line in r.stdout.split("\n") if line.strip()]


def generate(
    version: str,
    from_ref: str | None = None,
    commits: list[str] | None = None,
) -> str:
    """Build a markdown changelog entry. `commits` overrides git log (tests)."""
    if commits is None:
        commits = _git_log(from_ref)
    entries: dict[str, list[str]] = {name: [] for name, _ in SECTIONS}
    uncategorized: list[str] = []
    for msg in commits:
        m = COMMIT.match(msg)
        if m:
            section = next((s for s, tags in SECTIONS if m.group(1) in tags), "Chores")
            entries[section].append(m.group(2).rstrip("."))
        else:
            uncategorized.append(msg.rstrip("."))

    lines = [f"## [{version}] - {date.today().isoformat()}", ""]
    any_content = False
    for name, _ in SECTIONS:
        if entries[name]:
            lines.append(f"### {name}")
            for item in entries[name]:
                lines.append(f"- {item}")
            lines.append("")
            any_content = True
    if uncategorized:
        lines.append("### Other")
        for item in uncategorized:
            lines.append(f"- {item}")
        lines.append("")
        any_content = True
    if not any_content:
        lines.append("_No changes._")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="version for this entry, e.g. 0.7.0")
    ap.add_argument("--from", dest="from_ref", help="git ref to start from (default: last tag)")
    ap.add_argument("--write", action="store_true", help="prepend entry to CHANGELOG.md")
    ap.add_argument("--dir", default=".", help="project dir")
    args = ap.parse_args()

    from_ref = args.from_ref or last_tag()
    if from_ref:
        print(f"# from {from_ref}", file=sys.stderr)
    entry = generate(args.version, from_ref=from_ref)

    if args.write:
        ch = Path(args.dir) / "CHANGELOG.md"
        header = "# Changelog\n\n"
        if ch.exists():
            text = ch.read_text(encoding="utf-8")
            new_text = header + entry + "\n\n" + text[len(header):]
        else:
            new_text = header + entry + "\n"
        ch.write_text(new_text, encoding="utf-8")
        print(f"wrote {ch}")
    else:
        print(entry)


if __name__ == "__main__":
    main()
