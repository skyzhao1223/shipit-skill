"""shipit-skill CLI — one-pass launch pipeline.

Subcommands:
    preflight [--dir .] [--version ...] [--repo owner/name] [--online]   launch-readiness gap report
    init <dir> [--lang ...] [--server ...] [--pkg ...] [--force] [--dry-run]   scaffold a project
    ci [--lang ...] [--server ...] [--pkg ...] [--write path]   generate CI workflow
    bump patch|minor|major|set:X.Y.Z [--dir .] [--dry-run]   bump version + sync files
    release --lang ... --pkg ... [--how patch] [--repo ...] [--dry-run]   one-step release recipe
    publish --lang ... --pkg ... [--server ...] [--verify]   print registry publish commands
    check-promo --dir ... --version ... [--prs ...] [--no-links]   promo freshness + broken links
    check-glama --repo ... [--poll N] [--wait S]   Glama listing/badge check
    awesome-pr --upstream ... --repo ... --fork ... --branch ... [--title ...]   awesome PR recipe

Examples:
    shipit-skill preflight --dir ./my-tool
    shipit-skill init ./my-tool --server my-tool --pkg my-tool
    shipit-skill check-promo --dir promo --version 0.1.1 --prs 13600=open
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, cast

from shipit_skill import (
    __version__,
    awesome_pr,
    bump,
    ci,
    doctor,
    glama,
    preflight,
    promo_check,
    publish,
    release,
)


def _ask(prompt: str, default: str) -> str:
    """Interactive prompt when not a TTY-safe environment."""
    if not sys.stdin.isatty():
        return default
    try:
        val = input(f"{prompt} [{default}]: ").strip()
        return val or default
    except EOFError:
        return default


def _cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.dir).resolve()

    # interactive defaults
    if args.lang == "python" and not args.server:
        args.server = _ask("MCP server console-script name", "my-server")
    if args.pkg == "app":
        args.pkg = _ask("package / docker image name", target.name or "app")

    check_files = [".github/workflows/ci.yml", "Dockerfile", ".dockerignore", "promo/README.md"]
    existing = [f for f in check_files if (target / f).exists()]
    if existing and not args.force:
        print("Already exists (use --force to overwrite): " + ", ".join(existing))
        raise SystemExit(1)

    files: list[tuple[Path, str]] = []

    workflow = target / ".github" / "workflows"
    workflow.mkdir(parents=True, exist_ok=True)
    yaml = ci.generate_ci(args.lang, server=args.server, pkg=args.pkg)
    files.append((workflow / "ci.yml", yaml))

    if args.lang == "python" and args.server:
        tpl = Path(__file__).parent / "templates"
        docker = tpl / "Dockerfile"
        if docker.exists():
            files.append((target / "Dockerfile", docker.read_text(encoding="utf-8")
                          .format(name=args.pkg, server=args.server)))
        ignore = tpl / ".dockerignore"
        if ignore.exists():
            files.append((target / ".dockerignore", ignore.read_text(encoding="utf-8")))

        scripts = target / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        smoke = Path(__file__).parent / "mcp_smoke.py"
        if smoke.exists():
            files.append((scripts / "mcp_smoke.py", smoke.read_text(encoding="utf-8")))

    promo = target / "promo"
    promo.mkdir(parents=True, exist_ok=True)
    promo_tpl = Path(__file__).parent / "templates" / "promo" / "README.md"
    if promo_tpl.exists():
        files.append((promo / "README.md", promo_tpl.read_text(encoding="utf-8")))

    for path, content in files:
        if args.dry_run:
            print(f"(dry) would write {path}")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path}")

    cmd = f"shipit-skill publish --lang {args.lang} --pkg {args.pkg}"
    print(f"\nDone. Next: run `{cmd}` when ready.")


def _cmd_ci(args: argparse.Namespace) -> None:
    if args.release:
        yaml = ci.generate_release(args.lang, args.pkg)
    else:
        yaml = ci.generate_ci(args.lang, server=args.server, pkg=args.pkg)
    print(yaml, end="")
    if args.write:
        path = Path(args.write)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml, encoding="utf-8")
        print(f"\nwrote {path}", file=sys.stderr)


def _cmd_publish(args: argparse.Namespace) -> None:
    if args.execute:
        if args.lang == "python":
            publish.execute_python(args.pkg, args.server)
        else:
            publish.execute_typescript()
    elif args.lang == "python":
        publish.print_python_commands(args.pkg, args.server, args.verify)
    else:
        publish.print_typescript_commands()


def _cmd_preflight(args: argparse.Namespace) -> None:
    report = preflight.preflight(args.dir, version=args.version, repo=args.repo, online=args.online)
    if args.json:
        import json

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


def _cmd_bump(args: argparse.Namespace) -> None:
    old = bump.parse_version(args.dir)
    new = bump.bump(old, args.how) if not args.how.startswith("set:") else args.how[4:]
    for change in bump.set_version(args.dir, new, dry_run=args.dry_run):
        print(("(dry) " if args.dry_run else "") + change)
    print(f"\n{old} → {new}")
    if args.commit and not args.dry_run:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"chore: bump to {new}"], check=True)
        print(f"committed: bump to {new}")


def _cmd_release(args: argparse.Namespace) -> None:
    if args.execute:
        release.execute(args.lang, args.pkg, args.how, args.repo, args.dir,
                        args.title, args.server)
        return
    for cmd in release.release(
        args.lang, args.pkg, args.how, args.repo, args.dir,
        args.dry_run, args.title, args.server,
    ):
        print(cmd)
    print("\n# Commands above are guidance — review before running.")


def _cmd_check_promo(args: argparse.Namespace) -> None:
    known = {k: v for k, v in (kv.split("=") for kv in args.prs.split(",") if kv)}
    errors = promo_check.check_dir(
        args.dir,
        args.version,
        prs=known,
        check_links=not args.no_links,
    )
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


def _cmd_doctor(args: argparse.Namespace) -> None:
    checks = doctor.doctor()
    if args.json:
        import json

        print(json.dumps({"ok": all(c["ok"] for c in checks), "checks": checks}, indent=2))
    else:
        for c in checks:
            print(f"  {'✓' if c['ok'] else '✗'} {c['name']}: {c['detail']}")
        print(f"\nReady to release: {sum(1 for c in checks if c['ok'])}/"
              f"{len(checks)} checks passed")
    if not all(c["ok"] for c in checks):
        raise SystemExit(1)


def _cmd_check_glama(args: argparse.Namespace) -> None:
    import json as _json

    listed = glama.check_glama(args.repo, poll=args.poll, wait=args.wait)
    badge_ok = args.add_badge and glama.add_badge(args.repo, args.readme)
    if args.json:
        print(_json.dumps({
            "repo": args.repo,
            "listed": listed,
            "badge": "added" if badge_ok else ("skipped" if not args.add_badge else "failed"),
            "ok": listed,
        }, indent=2))
        if not listed:
            raise SystemExit(1)
        return
    if not listed:
        raise SystemExit(1)


def _cmd_awesome_pr(args: argparse.Namespace) -> None:
    if args.execute:
        if not (args.category and args.description and args.install):
            print("--execute requires --category, --description and --install",
                  file=sys.stderr)
            raise SystemExit(2)
        awesome_pr.execute(args.upstream, args.repo, args.fork, args.branch,
                           args.category, args.description, args.install, args.title)
        return
    print(awesome_pr.recipe(args.upstream, args.repo, args.fork, args.branch, args.title))


def _utf8_stdout() -> None:
    try:
        cast(Any, sys.stdout).reconfigure(encoding="utf-8")
        cast(Any, sys.stderr).reconfigure(encoding="utf-8")
    except Exception:
        pass


def _latest_pypi_version() -> str | None:
    """Return the newest shipit-skill on PyPI, or None if it can't be checked."""
    import json
    import urllib.request

    req = urllib.request.Request(
        "https://pypi.org/pypi/shipit-skill/json", headers={"User-Agent": "shipit-skill"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))["info"]["version"]
    except Exception:
        return None


def _check_upgrade() -> None:
    latest = _latest_pypi_version()
    if latest and latest != __version__:
        print(
            f"\n→ shipit-skill {latest} available (you have {__version__}); "
            "upgrade with `pip install -U shipit-skill`",
            file=sys.stderr,
        )


def main() -> None:
    _utf8_stdout()
    if sys.stdin.isatty():
        threading.Thread(target=_check_upgrade, daemon=True).start()
    ap = argparse.ArgumentParser(prog="shipit-skill", description=__doc__)
    ap.add_argument(
        "--version", action="version",
        version=f"shipit-skill {__version__}",
        help="print version and exit",
    )
    sub = ap.add_subparsers(dest="cmd")

    p_pre = sub.add_parser("preflight", help="launch-readiness gap report")
    p_pre.add_argument("--dir", default=".")
    p_pre.add_argument("--version", help="expected package version")
    p_pre.add_argument("--repo", help="owner/name for online checks")
    p_pre.add_argument("--online", action="store_true")
    p_pre.add_argument("--json", action="store_true")
    p_pre.set_defaults(fn=_cmd_preflight)

    p_init = sub.add_parser("init", help="scaffold a project for launch")
    p_init.add_argument("dir", help="target project directory")
    p_init.add_argument("--lang", default="python", choices=["python", "typescript"])
    p_init.add_argument("--server", help="MCP console-script name (python only)")
    p_init.add_argument("--pkg", default="app", help="package / docker image name")
    p_init.add_argument("--force", action="store_true", help="overwrite existing files")
    p_init.add_argument("--dry-run", action="store_true", help="preview without writing")
    p_init.set_defaults(fn=_cmd_init)

    p_ci = sub.add_parser("ci", help="generate a CI workflow")
    p_ci.add_argument("--lang", required=True, choices=["python", "typescript"])
    p_ci.add_argument("--server", help="MCP server console-script name (python)")
    p_ci.add_argument("--pkg", default="app")
    p_ci.add_argument("--write", help="write YAML to this path instead of stdout")
    p_ci.add_argument("--release", action="store_true", help="emit release.yml workflow")
    p_ci.set_defaults(fn=_cmd_ci)

    p_bump = sub.add_parser("bump", help="bump version + sync files")
    p_bump.add_argument("how", help="patch | minor | major | set:X.Y.Z")
    p_bump.add_argument("--dir", default=".")
    p_bump.add_argument("--dry-run", action="store_true")
    p_bump.add_argument("--commit", action="store_true", help="git add + commit")
    p_bump.set_defaults(fn=_cmd_bump)

    p_rel = sub.add_parser("release", help="one-step release recipe")
    p_rel.add_argument("--lang", required=True, choices=["python", "typescript"])
    p_rel.add_argument("--pkg", required=True)
    p_rel.add_argument("--how", default="patch")
    p_rel.add_argument("--repo", help="owner/name for GitHub Release")
    p_rel.add_argument("--dir", default=".")
    p_rel.add_argument("--server", help="MCP server name (python)")
    p_rel.add_argument("--title")
    p_rel.add_argument("--dry-run", action="store_true")
    p_rel.add_argument("--execute", action="store_true", help="actually run the release")
    p_rel.set_defaults(fn=_cmd_release)

    p_pub = sub.add_parser("publish", help="print registry publish commands")
    p_pub.add_argument("--lang", required=True, choices=["python", "typescript"])
    p_pub.add_argument("--pkg", required=True)
    p_pub.add_argument("--server")
    p_pub.add_argument("--verify", action="store_true")
    p_pub.add_argument("--execute", action="store_true", help="actually publish (token from env)")
    p_pub.set_defaults(fn=_cmd_publish)

    p_doctor = sub.add_parser("doctor", help="one-shot environment self-check")
    p_doctor.add_argument("--json", action="store_true", help="emit JSON")
    p_doctor.set_defaults(fn=_cmd_doctor)

    p_promo = sub.add_parser("check-promo", help="promo freshness + broken links")
    p_promo.add_argument("--dir", required=True)
    p_promo.add_argument("--version", required=True)
    p_promo.add_argument("--prs", default="")
    p_promo.add_argument("--no-links", action="store_true")
    p_promo.add_argument("--report", action="store_true", help="emit JSON report")
    p_promo.set_defaults(fn=_cmd_check_promo)

    p_glama = sub.add_parser("check-glama", help="check Glama listing + badge")
    p_glama.add_argument("--repo", required=True)
    p_glama.add_argument("--poll", type=int, default=0)
    p_glama.add_argument("--wait", type=int, default=40)
    p_glama.add_argument("--add-badge", action="store_true",
                         help="write badge to README when listed")
    p_glama.add_argument("--readme", default="README.md")
    p_glama.add_argument("--json", action="store_true", help="emit JSON result")
    p_glama.set_defaults(fn=_cmd_check_glama)

    p_pr = sub.add_parser("awesome-pr", help="print awesome-list submission recipe")
    p_pr.add_argument("--upstream", required=True)
    p_pr.add_argument("--repo", required=True)
    p_pr.add_argument("--fork", required=True)
    p_pr.add_argument("--branch", required=True)
    p_pr.add_argument("--title", default="")
    p_pr.add_argument("--category", help="heading to insert under (with --execute)")
    p_pr.add_argument("--description", help="one-line description (with --execute)")
    p_pr.add_argument("--install", help="install command, e.g. npx foo (with --execute)")
    p_pr.add_argument("--execute", action="store_true", help="actually open the PR via gh")
    p_pr.set_defaults(fn=_cmd_awesome_pr)

    _enable_completions(ap)

    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help()
        raise SystemExit(2)
    args.fn(args)


def _enable_completions(ap: argparse.ArgumentParser) -> None:
    """Register shell completions when argcomplete is installed (best effort)."""
    try:
        import argcomplete  # type: ignore

        argcomplete.autocomplete(ap)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
