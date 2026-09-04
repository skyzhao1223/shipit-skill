"""Preflight — scan a repo and report launch-readiness gaps.

CLI:
    python -m shipit_skill.preflight --dir . [--version 0.1.1] [--repo owner/name]
    python -m shipit_skill.preflight --dir . --json

Checks (offline unless --online):
  - CI workflow present?
  - Dockerfile present?  .dockerignore present?
  - package manifest (pyproject.toml / package.json) + version?
  - Git remote set?
  - promo/ dir present?  promo versions consistent with package version?
Exit 0 if all OK, 1 if any gap (list them).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

SEMVER = re.compile(r"(?<![\d.])(?:v)?0\.\d+\.\d+\b")
GITHUB_URL = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+")


def _has(path: Path) -> bool:
    return path.exists()


def _git_remote(dir_: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(dir_), "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except FileNotFoundError:
        return None


def _package_version(dir_: Path) -> str | None:
    py = dir_ / "pyproject.toml"
    if py.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', py.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    js = dir_ / "package.json"
    if js.exists():
        m = re.search(r'"version"\s*:\s*"([^"]+)"', js.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    return None


def _promo_versions(dir_: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    promo = dir_ / "promo"
    if not promo.is_dir():
        return found
    for f in sorted(promo.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        for m in SEMVER.finditer(text):
            found.append((f.name, m.group(0).lstrip("v")))
    return found


def preflight(
    dir_: str,
    version: str | None = None,
    repo: str | None = None,
    online: bool = False,
) -> dict:
    d = Path(dir_).resolve()
    gaps: list[str] = []
    ok: list[str] = []

    # 1. CI
    ci = _has(d / ".github/workflows/ci.yml") or _has(d / ".github/workflows")
    (ok if ci else gaps).append("CI workflow" if ci else "CI workflow (add .github/workflows/)")

    # 2. Docker artifacts
    docker = _has(d / "Dockerfile")
    if docker:
        ok.append("Dockerfile")
    else:
        gaps.append("Dockerfile (needed for Glama/containers)")
    if not _has(d / ".dockerignore"):
        gaps.append(".dockerignore")

    # 3. package manifest + version
    pkg_ver = _package_version(d)
    if pkg_ver is None:
        gaps.append("package manifest (pyproject.toml / package.json) with version")
    else:
        ok.append(f"package version {pkg_ver}")
        if version and version != pkg_ver:
            gaps.append(f"CLI --version {version} != manifest {pkg_ver}")

    # 4. git remote
    remote = _git_remote(d)
    if remote:
        ok.append(f"git remote origin ({remote})")
    else:
        gaps.append("git remote origin (unset)")

    # 5. promo
    promo_files = list((d / "promo").glob("*.md")) if (d / "promo").is_dir() else []
    if promo_files:
        ok.append(f"promo/ dir ({len(promo_files)} files)")
    else:
        gaps.append("promo/ dir (missing)")

    # 5b. promo version consistency
    if pkg_ver and promo_files:
        stale = [(f, v) for f, v in _promo_versions(d) if v != pkg_ver]
        if stale:
            gap = "; ".join(f"{f}→{v}" for f, v in stale)
            gaps.append(f"promo stale versions ({gap})")
        else:
            ok.append("promo versions consistent")

    # 6. online checks (optional)
    if online:
        if repo:
            ok.append(f"repo arg {repo} (run check-glama for live listing status)")
        gh_rel = subprocess.run(
            ["gh", "release", "list", "--repo", repo or "", "--limit", "1"],
            capture_output=True, text=True,
        ) if repo else None
        if gh_rel is not None and gh_rel.returncode == 0 and gh_rel.stdout.strip():
            first = gh_rel.stdout.strip().splitlines()[0].split(chr(9))[0]
            ok.append(f"GitHub release ({first})")
        elif repo:
            gaps.append("GitHub release (none found — run `shipit-skill release`)")

    return {"dir": str(d), "ok": ok, "gaps": gaps, "ready": not gaps}


def _utf8_stdout() -> None:
    try:
        cast(Any, sys.stdout).reconfigure(encoding="utf-8")
        cast(Any, sys.stderr).reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".", help="repo to scan")
    ap.add_argument("--version", help="expected package version")
    ap.add_argument("--repo", help="owner/repo for online checks")
    ap.add_argument("--online", action="store_true", help="include network checks (gh)")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args()

    report = preflight(args.dir, version=args.version, repo=args.repo, online=args.online)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for line in report["ok"]:
            print(f"  ✓ {line}")
        for line in report["gaps"]:
            print(f"  ✗ {line}")
        print(f"\nReady: {len(report['ok'])} ok, {len(report['gaps'])} gaps → "
              + ("SHIP IT 🚀" if report["ready"] else "fix gaps first"))

    if not report["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
