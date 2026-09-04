"""shipit-skill CLI — one-pass launch pipeline.

Subcommands:
    init <dir>                 scaffold CI / Dockerfile / .dockerignore / promo / smoke
    ci <dir> --lang ...        write .github/workflows/ci.yml (from generated template)
    publish --lang ... --pkg ...   print registry publish commands
    check-promo --dir ... --version ...   promo freshness + broken-link check
    check-glama --repo ...     Glama listing/badge check (with optional polling)
    awesome-pr ...             print awesome-list submission recipe

Examples:
    shipit-skill init ./my-tool --server my-tool --pkg my-tool
    shipit-skill check-promo --dir promo --version 0.1.1 --prs 13600=open
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from shipit_skill import awesome_pr, ci, glama, promo_check, publish


def _cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    # CI workflow
    workflow = target / ".github" / "workflows"
    workflow.mkdir(parents=True, exist_ok=True)
    yaml = ci.generate_ci(args.lang, server=args.server, pkg=args.pkg)
    (workflow / "ci.yml").write_text(yaml, encoding="utf-8")
    print(f"wrote {workflow / 'ci.yml'}")

    # Dockerfile + .dockerignore (python server only)
    if args.lang == "python" and args.server:
        tpl_dir = Path(__file__).parent / "templates"
        docker = tpl_dir / "Dockerfile"
        ignore = tpl_dir / ".dockerignore"
        if docker.exists():
            content = docker.read_text(encoding="utf-8").format(name=args.pkg, server=args.server)
            (target / "Dockerfile").write_text(content, encoding="utf-8")
            print(f"wrote {target / 'Dockerfile'}")
        if ignore.exists():
            shutil.copy(ignore, target / ".dockerignore")
            print(f"wrote {target / '.dockerignore'}")

        # mcp_smoke.py into the project's scripts dir
        scripts = target / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        smoke = Path(__file__).parent / "mcp_smoke.py"
        if smoke.exists():
            shutil.copy(smoke, scripts / "mcp_smoke.py")
            print(f"wrote {scripts / 'mcp_smoke.py'}")

    # promo skeleton
    promo = target / "promo"
    promo.mkdir(parents=True, exist_ok=True)
    promo_tpl = Path(__file__).parent / "templates" / "promo" / "README.md"
    if promo_tpl.exists():
        shutil.copy(promo_tpl, promo / "README.md")
        print(f"wrote {promo / 'README.md'}")

    cmd = f"shipit-skill publish --lang {args.lang} --pkg {args.pkg}"
    print(f"\nDone. Next: run `{cmd}` when ready.")


def _cmd_ci(args: argparse.Namespace) -> None:
    yaml = ci.generate_ci(args.lang, server=args.server, pkg=args.pkg)
    print(yaml, end="")
    if args.write:
        path = Path(args.write)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml, encoding="utf-8")
        print(f"\nwrote {path}", file=sys.stderr)


def _cmd_publish(args: argparse.Namespace) -> None:
    if args.lang == "python":
        publish.print_python_commands(args.pkg, args.server, args.verify)
    else:
        publish.print_typescript_commands()


def _cmd_check_promo(args: argparse.Namespace) -> None:
    known = {k: v for k, v in (kv.split("=") for kv in args.prs.split(",") if kv)}
    errors = promo_check.check_dir(
        args.dir,
        args.version,
        prs=known,
        check_links=not args.no_links,
    )
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("OK: no stale versions, unknown PRs, or broken links.")


def _cmd_check_glama(args: argparse.Namespace) -> None:
    if not glama.check_glama(args.repo, poll=args.poll, wait=args.wait):
        raise SystemExit(1)


def _cmd_awesome_pr(args: argparse.Namespace) -> None:
    print(awesome_pr.recipe(args.upstream, args.repo, args.fork, args.branch, args.title))


def main() -> None:
    ap = argparse.ArgumentParser(prog="shipit-skill", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="scaffold a project for launch")
    p_init.add_argument("dir", help="target project directory")
    p_init.add_argument("--lang", default="python", choices=["python", "typescript"])
    p_init.add_argument("--server", help="MCP console-script name (python only)")
    p_init.add_argument("--pkg", default="app", help="package / docker image name")
    p_init.set_defaults(fn=_cmd_init)

    p_ci = sub.add_parser("ci", help="generate a CI workflow")
    p_ci.add_argument("--lang", required=True, choices=["python", "typescript"])
    p_ci.add_argument("--server", help="MCP server console-script name (python)")
    p_ci.add_argument("--pkg", default="app")
    p_ci.add_argument("--write", help="write YAML to this path instead of stdout")
    p_ci.set_defaults(fn=_cmd_ci)

    p_pub = sub.add_parser("publish", help="print registry publish commands")
    p_pub.add_argument("--lang", required=True, choices=["python", "typescript"])
    p_pub.add_argument("--pkg", required=True)
    p_pub.add_argument("--server")
    p_pub.add_argument("--verify", action="store_true")
    p_pub.set_defaults(fn=_cmd_publish)

    p_promo = sub.add_parser("check-promo", help="promo freshness + broken links")
    p_promo.add_argument("--dir", required=True)
    p_promo.add_argument("--version", required=True)
    p_promo.add_argument("--prs", default="")
    p_promo.add_argument("--no-links", action="store_true")
    p_promo.set_defaults(fn=_cmd_check_promo)

    p_glama = sub.add_parser("check-glama", help="check Glama listing + badge")
    p_glama.add_argument("--repo", required=True)
    p_glama.add_argument("--poll", type=int, default=0)
    p_glama.add_argument("--wait", type=int, default=40)
    p_glama.set_defaults(fn=_cmd_check_glama)

    p_pr = sub.add_parser("awesome-pr", help="print awesome-list submission recipe")
    p_pr.add_argument("--upstream", required=True)
    p_pr.add_argument("--repo", required=True)
    p_pr.add_argument("--fork", required=True)
    p_pr.add_argument("--branch", required=True)
    p_pr.add_argument("--title", default="")
    p_pr.set_defaults(fn=_cmd_awesome_pr)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
