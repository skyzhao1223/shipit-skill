"""Publish helper — build, verify fresh install, and emit publish commands.

CLI:
    python -m shipit_skill.publish --lang python [--pkg zspace-cli] [--server zs-mcp]
    python -m shipit_skill.publish --lang typescript [--pkg @org/cli]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


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


def print_typescript_commands() -> None:
    print(
        "# Publish (set NPM_TOKEN=<granular token, bypass-2fa>)\n"
        "npm publish --//registry.npmjs.org/:_authToken=\"$NPM_TOKEN\" --access public"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["python", "typescript"])
    ap.add_argument("--pkg", required=True, help="package name")
    ap.add_argument("--server", help="MCP console script name (python)")
    ap.add_argument("--verify", action="store_true", help="run fresh-install check")
    args = ap.parse_args()

    if args.lang == "python":
        print_python_commands(args.pkg, args.server, args.verify)
    else:
        print_typescript_commands()


if __name__ == "__main__":
    main()
