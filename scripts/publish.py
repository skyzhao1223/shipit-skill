#!/usr/bin/env python3
"""Publish helper: build, verify fresh install, and emit publish commands.

Usage:
    python3 scripts/publish.py --lang python [--pkg zspace-cli] [--server zs-mcp]
    python3 scripts/publish.py --lang typescript [--pkg @org/cli]

Prints the exact publish commands (needs a user-supplied token — never stored).
Also runs a fresh-install verification in a temp venv when --verify.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def verify_python(pkg: str, server: str | None, extras: str) -> None:
    tmp = tempfile.mkdtemp(prefix="shipit-")
    run([sys.executable, "-m", "venv", f"{tmp}/venv"])
    pip = f"{tmp}/venv/bin/pip"
    run([pip, "install", "-q", extras])
    importlib = f"{tmp}/venv/bin/python"
    subprocess.run([importlib, "-c", f"import importlib.metadata as m; print('installed', m.version('{pkg}'))"], check=True)
    if server:
        init = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
        handshake = f"printf '{init}' | {tmp}/venv/bin/{server} 2>/dev/null | python3 -c \"import sys,json; [print(json.loads(l)['result'].get('serverInfo')) for l in sys.stdin if l.strip()]\""
        subprocess.run(["bash", "-c", handshake], check=True)
    print(f"fresh-install OK (venv: {tmp}/venv)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["python", "typescript"])
    ap.add_argument("--pkg", required=True, help="package name")
    ap.add_argument("--server", help="MCP console script name (python)")
    ap.add_argument("--verify", action="store_true", help="run fresh-install check")
    args = ap.parse_args()

    if args.lang == "python":
        print(f"# Build\npython3 -m build")
        print(f"# Publish (set PYPI_TOKEN=<pypi-... token, Upload scope on {args.pkg}>)\n"
              f"python3 -m twine upload --repository-url https://upload.pypi.org/legacy/ \\\n"
              f"  --username __token__ --password \"$PYPI_TOKEN\" dist/{args.pkg}-*.tar.gz dist/{args.pkg}-*.whl")
        if args.verify:
            verify_python(args.pkg, args.server, args.pkg)
    else:
        print(f"# Publish (set NPM_TOKEN=<granular token, bypass-2fa>)\n"
              f"npm publish --//registry.npmjs.org/:_authToken=\"$NPM_TOKEN\" --access public")


if __name__ == "__main__":
    main()
