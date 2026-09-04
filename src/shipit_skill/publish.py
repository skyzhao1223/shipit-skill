"""Publish helper — build, publish, verify.

CLI:
    python -m shipit_skill.publish --lang python [--pkg zspace-cli] [--server zs-mcp]
    python -m shipit_skill.publish --lang python --pkg zspace-cli --execute   # actually publish
    python -m shipit_skill.publish --lang typescript [--pkg @org/cli] [--execute]

Without --execute, prints the exact commands (needs a user-supplied token —
never stored). With --execute, runs build + registry publish (reading token from
env) + fresh-install verification.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _build() -> None:
    if not Path("dist").exists() or not any(Path("dist").glob("*.whl")):
        _run([sys.executable, "-m", "build"])


def verify_python(pkg: str, server: str | None, extras: str) -> None:
    """Fresh-install from the registry into a temp venv and smoke-test it."""
    tmp = tempfile.mkdtemp(prefix="shipit-")
    venv = f"{tmp}/venv"
    _run([sys.executable, "-m", "venv", venv])
    _run([f"{venv}/bin/pip", "install", "-q", extras])
    _run(
        [f"{venv}/bin/python", "-c",
         f"import importlib.metadata as m; print('installed', m.version('{pkg}'))"]
    )
    if server:
        init = (
            '{"jsonrpc":"2.0","id":1,"method":"initialize",'
            '"params":{"protocolVersion":"2024-11-05","capabilities":{},'
            '"clientInfo":{"name":"smoke","version":"0"}}}\n'
            '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
        )
        handshake = (
            f"printf '{init}' | {venv}/bin/{server} 2>/dev/null | python3 -c "
            "\"import sys,json; "
            "[print(json.loads(l)['result'].get('serverInfo')) for l in sys.stdin if l.strip()]\""
        )
        subprocess.run(["bash", "-c", handshake], check=True)
    print(f"fresh-install OK (venv: {venv})")


def print_python_commands(pkg: str, server: str | None, verify: bool) -> None:
    print("# Build\npython3 -m build")
    print(
        f"# Publish (set PYPI_TOKEN=<pypi-... token, Upload scope on {pkg}>)\n"
        f"python3 -m twine upload --repository-url https://upload.pypi.org/legacy/ \\\n"
        f"  --username __token__ --password \"$PYPI_TOKEN\" "
        f"dist/{pkg}-*.tar.gz dist/{pkg}-*.whl"
    )
    if verify:
        verify_python(pkg, server, pkg)


def execute_python(pkg: str, server: str | None) -> None:
    """Actually build + publish to PyPI (token from PYPI_TOKEN env) + verify."""
    token = os.environ.get("PYPI_TOKEN")
    if not token:
        raise SystemExit("PYPI_TOKEN env var required for --execute")
    _build()
    _run([
        sys.executable, "-m", "twine", "upload",
        "--repository-url", "https://upload.pypi.org/legacy/",
        "--username", "__token__", "--password", token,
        *sorted(str(p) for p in Path("dist").glob("*.tar.gz")),
        *sorted(str(p) for p in Path("dist").glob("*.whl")),
    ])
    verify_python(pkg, server, pkg)


def print_typescript_commands() -> None:
    print(
        "# Publish (set NPM_TOKEN=<granular token, bypass-2fa>)\n"
        "npm publish --//registry.npmjs.org/:_authToken=\"$NPM_TOKEN\" --access public"
    )


def execute_typescript() -> None:
    token = os.environ.get("NPM_TOKEN")
    if not token:
        raise SystemExit("NPM_TOKEN env var required for --execute")
    env = {**os.environ, "NPM_TOKEN": token}
    subprocess.run(
        ["npm", "publish", "--//registry.npmjs.org/:_authToken=" + token, "--access", "public"],
        check=True, env=env,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["python", "typescript"])
    ap.add_argument("--pkg", required=True, help="package name")
    ap.add_argument("--server", help="MCP console script name (python)")
    ap.add_argument("--verify", action="store_true", help="run fresh-install check")
    ap.add_argument("--execute", action="store_true", help="actually publish (token from env)")
    args = ap.parse_args()

    if args.lang == "python":
        if args.execute:
            execute_python(args.pkg, args.server)
        else:
            print_python_commands(args.pkg, args.server, args.verify)
    else:
        if args.execute:
            execute_typescript()
        else:
            print_typescript_commands()


if __name__ == "__main__":
    main()
