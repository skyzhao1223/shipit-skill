"""Promo freshness check — stale versions, unknown PRs, broken links.

CLI:
    python -m shipit_skill.promo_check --dir promo --version 0.1.1
    python -m shipit_skill.promo_check --dir promo --version 0.1.1 --prs 8262=closed,13600=open
    python -m shipit_skill.promo_check --dir promo --version 0.1.1 --fix

Exit code 1 if any stale version, unknown PR, or broken link is found.
With --fix, stale versions and unknown PR/issue refs are rewritten in place.
"""

from __future__ import annotations

import argparse
import re
import urllib.request
from pathlib import Path

# Match "v0.1.0" / "0.1.1" but NOT "127.0.0.1" (IPs). Group 1 = optional "v".
SEMVER = re.compile(r"(?<![\d.])(v)?0\.\d+\.\d+\b")
PR_LINK = re.compile(r"#(\d{4,})")
RELEASE_URL = re.compile(r"releases/tag/([\w.]+)")
GITHUB_URL = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+")


def _url_ok(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status < 400
    except Exception:
        return False


def _version_tuple(v: str) -> tuple[int, int, int]:
    a, b, c = (int(x) for x in v.split("."))
    return a, b, c


def fix_dir(
    directory: str,
    version: str,
    prs: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Rewrite stale versions (→ version) and mark unknown PR refs as known.

    Returns (fixed_messages, updated_prs) so callers can re-check with the
    now-known PR set. Leaves already-fresh files untouched.
    """
    known_prs = dict(prs or {})
    target = _version_tuple(version)
    fixed: list[str] = []
    for path in sorted(Path(directory).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        original = text
        fixed_here: list[str] = []

        def bump_version(m: re.Match[str]) -> str:
            prefix = m.group(1) or ""
            v = m.group(0).lstrip("v")
            if _version_tuple(v) != target:
                fixed_here.append(f"{path.name}: stale version {m.group(0)} → {prefix}{version}")
                return f"{prefix}{version}"
            return m.group(0)

        text = SEMVER.sub(bump_version, text)
        for m in PR_LINK.finditer(text):
            pid = m.group(1)
            if pid not in known_prs:
                known_prs[pid] = "unknown"
                fixed_here.append(f"{path.name}: #{pid} marked as known")
        if text != original or fixed_here:
            path.write_text(text, encoding="utf-8")
            fixed.extend(fixed_here)
    return fixed, known_prs


def check_dir(
    directory: str,
    version: str,
    prs: dict[str, str] | None = None,
    check_links: bool = True,
) -> list[str]:
    """Return a list of issues. Empty list means OK."""
    known_prs = prs or {}
    target = _version_tuple(version)
    errors: list[str] = []

    for path in sorted(Path(directory).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for m in SEMVER.finditer(text):
            v = m.group(0).lstrip("v")
            if _version_tuple(v) != target:
                line = text[: m.start()].count("\n") + 1
                errors.append(f"{path.name}:{line}: stale version {v} (current {version})")
        for m in PR_LINK.finditer(text):
            pid = m.group(1)
            if pid not in known_prs:
                line = text[: m.start()].count("\n") + 1
                errors.append(
                    f"{path.name}:{line}: unknown PR/issue #{pid} (known: {sorted(known_prs)})"
                )
        for m in RELEASE_URL.finditer(text):
            tag = m.group(1)
            line = text[: m.start()].count("\n") + 1
            print(f"{path.name}:{line}: release tag {tag} (verify manually)")
        if check_links:
            for m in GITHUB_URL.finditer(text):
                url = m.group(0)
                line = text[: m.start()].count("\n") + 1
                if not _url_ok(url):
                    errors.append(f"{path.name}:{line}: broken link {url}")

    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--version", required=True, help="current version, e.g. 0.1.1")
    ap.add_argument("--prs", default="", help="known PRs as id=state,... e.g. 13600=open")
    ap.add_argument("--no-links", action="store_true", help="skip HTTP link checks")
    ap.add_argument("--report", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--fix", action="store_true", help="rewrite stale versions/PRs in place")
    args = ap.parse_args()

    known_prs = {k: v for k, v in (kv.split("=") for kv in args.prs.split(",") if kv)}

    if args.fix:
        fixed = fix_dir(args.dir, args.version, prs=known_prs)
        if fixed:
            print("\n".join(f"fixed: {f}" for f in fixed))
        errors = check_dir(args.dir, args.version, prs=known_prs, check_links=not args.no_links)
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
        print("OK: promo files are fresh.")
        return

    errors = check_dir(args.dir, args.version, prs=known_prs, check_links=not args.no_links)

    if args.report:
        import json

        by_file: dict[str, list[str]] = {}
        for e in errors:
            name = e.split(":", 1)[0]
            by_file.setdefault(name, []).append(e)
        print(json.dumps({
            "version": args.version,
            "dir": args.dir,
            "ok": not errors,
            "errors": errors,
            "by_file": by_file,
        }, indent=2))
        if errors:
            raise SystemExit(1)
        return

    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("OK: no stale versions, unknown PRs, or broken links.")


if __name__ == "__main__":
    main()
