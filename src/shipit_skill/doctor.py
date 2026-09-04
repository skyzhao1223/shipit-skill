"""Doctor — environment self-check before running a release.

CLI:
    python -m shipit_skill.doctor [--json]

Exits 0 if the local machine is ready to publish (gh authed, tokens set,
clean tree on main), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, cast

from shipit_skill import __version__


def _utf8_stdout() -> None:
    try:
        cast(Any, sys.stdout).reconfigure(encoding="utf-8")
        cast(Any, sys.stderr).reconfigure(encoding="utf-8")
    except Exception:
        pass


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.returncode, r.stdout.strip()
    except Exception:
        return 1, ""


def _gh_available() -> bool:
    return _run(["gh", "--version"])[0] == 0


def _gh_authed() -> bool:
    return _run(["gh", "auth", "status"])[0] == 0


def _git_remote() -> str:
    _, out = _run(["git", "remote", "get-url", "origin"])
    return out or "(none)"


def _git_branch() -> str:
    _, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return out or "(none)"


def _git_dirty() -> bool:
    _, out = _run(["git", "status", "--porcelain"])
    return bool(out)


def _env_flag(name: str) -> bool:
    return bool(os.environ.get(name))


def _importable(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def _which(bin_: str) -> bool:
    import shutil

    return shutil.which(bin_) is not None


def doctor() -> list[dict[str, Any]]:
    """Return the list of environment checks (ok/detail per item)."""
    checks: list[dict[str, Any]] = []
    gh_ok = _gh_available() and _gh_authed()
    checks.append({
        "name": "gh CLI installed + authed",
        "ok": gh_ok,
        "detail": "ok" if gh_ok else "missing or unauthenticated",
    })
    checks.append({
        "name": "PYPI_TOKEN set",
        "ok": _env_flag("PYPI_TOKEN"),
        "detail": "set" if _env_flag("PYPI_TOKEN") else "missing (needed for --execute)",
    })
    checks.append({
        "name": "NPM_TOKEN set",
        "ok": _env_flag("NPM_TOKEN"),
        "detail": "set" if _env_flag("NPM_TOKEN") else "missing (needed for TS --execute)",
    })
    checks.append({
        "name": "git remote origin",
        "ok": _git_remote() != "(none)",
        "detail": _git_remote(),
    })
    checks.append({
        "name": "branch is main",
        "ok": _git_branch() == "main",
        "detail": _git_branch(),
    })
    checks.append({
        "name": "working tree clean",
        "ok": not _git_dirty(),
        "detail": "clean" if not _git_dirty() else "uncommitted changes",
    })
    checks.append({
        "name": "python version",
        "ok": True,
        "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    })
    checks.append({
        "name": "build module importable",
        "ok": _importable("build"),
        "detail": "ok" if _importable("build") else "missing (pip install build)",
    })
    checks.append({
        "name": "twine module importable",
        "ok": _importable("twine"),
        "detail": "ok" if _importable("twine") else "missing (pip install twine)",
    })
    checks.append({
        "name": "node + npm available",
        "ok": _which("node") and _which("npm"),
        "detail": "ok" if _which("node") and _which("npm") else "missing node/npm",
    })
    checks.append({
        "name": "version",
        "ok": True,
        "detail": __version__,
    })
    return checks


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    checks = doctor()
    if args.json:
        print(json.dumps({"ok": all(c["ok"] for c in checks), "checks": checks}, indent=2))
    else:
        for c in checks:
            print(f"  {'✓' if c['ok'] else '✗'} {c['name']}: {c['detail']}")
        print(f"\nReady to release: {sum(1 for c in checks if c['ok'])}/"
              f"{len(checks)} checks passed")
    if not all(c["ok"] for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
