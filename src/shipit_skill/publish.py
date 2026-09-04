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


_PERMANENT_MARKERS = (
    "file already exists",
    "File already exists",
    "403",
    "Invalid or non-existent authentication",
    "invalid or non-existent",
    "409",
    "Version already exists",
    "E404",
    "npm ERR! 404",
    "Unauthorized",
)


def _is_permanent(output: str) -> bool:
    return any(marker.lower() in output.lower() for marker in _PERMANENT_MARKERS)


def _run_with_retry(cmd: list[str], *, tries: int = 3, backoff: float = 2.0,
                    env: dict[str, str] | None = None) -> None:
    """Run an upload command, retrying transient failures with backoff.

    Permanent errors (file already exists, auth failures, 403/404/409) are
    surfaced immediately without retries.
    """
    import time

    for attempt in range(1, tries + 1):
        try:
            subprocess.run(cmd, check=True, env=env)
            return
        except subprocess.CalledProcessError as e:
            output = (e.stderr or "") if isinstance(e.stderr, str) else ""
            if _is_permanent(output):
                raise
            if attempt < tries:
                print(f"  ⚠ upload attempt {attempt}/{tries} failed — retrying in "
                      f"{backoff * attempt}s")
                time.sleep(backoff * attempt)
            else:
                raise


def diagnose(lang: str, output: str) -> str | None:
    """Return a one-line actionable hint for a failed publish, or None."""
    low = output.lower()
    if "file already exists" in low or "already exists" in low:
        return ("version already on the registry — bump the version "
                "(release --how patch) or it's a re-run")
    if "403" in low or "invalid or non-existent authentication" in low:
        return ("bad token — PyPI tokens start 'pypi-'; scope it to the package "
                "with Upload permission")
    if "401" in low or "unauthorized" in low:
        return ("token rejected — check NPM_TOKEN scope / bypass-2FA, "
                "or PYPI_TOKEN upload scope")
    if "404" in low:
        return ("not found — scoped npm package? the org must exist; for PyPI "
                "the package name may be taken")
    if "409" in low or "conflict" in low:
        return "conflict — the version/tag already exists; re-run will skip"
    if "network" in low or "timed out" in low or "connection" in low:
        return "transient network failure — re-run the same command to retry"
    if lang == "typescript" and "no bin" in low:
        return "packaged CLI has no bin entry — add 'bin' to package.json"
    return None


def _build() -> None:
    import shutil

    if Path("dist").exists() and any(Path("dist").glob("*.whl")):
        print("cleaning stale dist/ artifacts before build")
        shutil.rmtree("dist", ignore_errors=True)
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
    try:
        _run_with_retry([
            sys.executable, "-m", "twine", "upload",
            "--repository-url", "https://upload.pypi.org/legacy/",
            "--username", "__token__", "--password", token,
            *sorted(str(p) for p in Path("dist").glob("*.tar.gz")),
            *sorted(str(p) for p in Path("dist").glob("*.whl")),
        ])
    except subprocess.CalledProcessError as e:
        hint = diagnose("python", e.stderr or "")
        print(f"  ✗ hint: {hint}" if hint else "  ✗ (no hint — see full error above)")
        raise
    verify_python(pkg, server, pkg)


def print_typescript_commands() -> None:
    print(
        "# Publish (set NPM_TOKEN=<granular token, bypass-2fa>)\n"
        "npm publish --//registry.npmjs.org/:_authToken=\"$NPM_TOKEN\" --access public"
    )


def verify_typescript(pkg: str) -> None:
    """npm-pack, fresh-install into a temp dir, then smoke-test the CLI binary."""
    tmp = tempfile.mkdtemp(prefix="shipit-ts-")
    tarball = subprocess.run(
        ["npm", "pack", "--json"], capture_output=True, text=True
    )
    if tarball.returncode != 0:
        raise SystemExit(f"npm pack failed: {tarball.stderr.strip()}")
    import json

    filename = json.loads(tarball.stdout)[0]["filename"]
    subprocess.run(
        ["npm", "init", "-y"], cwd=tmp, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["npm", "install", "-q", str(Path(filename).resolve())], cwd=tmp, check=True
    )
    bin_name = pkg.split("/")[-1] if pkg.startswith("@") else pkg
    r = subprocess.run(
        ["npx", "--prefix", tmp, bin_name, "--version"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise SystemExit(f"fresh-install smoke failed for {bin_name}: {r.stderr.strip()}")
    print(f"fresh-install OK (dir: {tmp}) → {bin_name} {r.stdout.strip()}")


def execute_typescript(pkg: str = "app") -> None:
    token = os.environ.get("NPM_TOKEN")
    if not token:
        raise SystemExit("NPM_TOKEN env var required for --execute")
    env = {**os.environ, "NPM_TOKEN": token}
    try:
        _run_with_retry(
            ["npm", "publish", "--//registry.npmjs.org/:_authToken=" + token,
             "--access", "public"],
            env=env,
        )
    except subprocess.CalledProcessError as e:
        hint = diagnose("typescript", e.stderr or "")
        print(f"  ✗ hint: {hint}" if hint else "  ✗ (no hint — see full error above)")
        raise
    verify_typescript(pkg)


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
            execute_typescript(args.pkg)
        else:
            print_typescript_commands()


if __name__ == "__main__":
    main()
