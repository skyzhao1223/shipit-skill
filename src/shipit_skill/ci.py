"""CI workflow generator — shared library + CLI.

Usage (CLI):
    python -m shipit_skill.ci --lang python [--server zs-mcp] [--pkg app]
    python -m shipit_skill.ci --lang typescript

Or from Python:
    from shipit_skill.ci import generate_ci
    print(generate_ci("python", server="zs-mcp", pkg="app"))
"""

from __future__ import annotations

import argparse

# ruff: noqa: E501

PY_CI = """name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [{py_versions}]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}
          cache: pip
      - run: pip install -e ".[dev]"
        if: matrix.python-version == '{base_py}'
      - run: pip install -e ".[mcp,dev]"
        if: matrix.python-version != '{base_py}'
      - run: ruff check src tests
      - run: pytest -q
{server_block}"""

PY_SERVER_BLOCK = """
  docker:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t {pkg} .
      - name: MCP handshake (initialize + tools/list)
        run: |
          set +e
          {{
            printf '{{"jsonrpc":"2.0","id":1,"method":"initialize","params":{{"protocolVersion":"2024-11-05","capabilities":{{}},"clientInfo":{{"name":"smoke","version":"0"}}}}}}\\n{{"jsonrpc":"2.0","method":"notifications/initialized"}}\\n{{"jsonrpc":"2.0","id":2,"method":"tools/list"}}\\n'
            sleep 1
          }} | docker run --rm -i {pkg} >/tmp/mcp-out.txt 2>/tmp/mcp-err.txt
          rc=$?
          echo "exit=$rc"; echo "--- stderr ---"; cat /tmp/mcp-err.txt
          echo "--- stdout (first 500) ---"; head -c 500 /tmp/mcp-out.txt; echo
          [ $rc -eq 0 ] && python3 scripts/mcp_smoke.py < /tmp/mcp-out.txt
"""

TS_CI = """name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: npm
      - run: npm ci
      - run: npm run build --workspaces --if-present
      - run: npm test --workspaces --if-present
"""


def generate_ci(
    lang: str,
    server: str | None = None,
    pkg: str = "app",
    py_versions: str = '"3.9", "3.12"',
    base_py: str = "3.9",
) -> str:
    """Generate a CI workflow YAML."""
    if lang == "typescript":
        return TS_CI
    server_block = ""
    if server:
        server_block = PY_SERVER_BLOCK.format(pkg=pkg)
    return PY_CI.format(
        py_versions=py_versions,
        base_py=base_py,
        server_block=server_block,
    )


RELEASE_YML = """name: Release

on:
  workflow_dispatch:
    inputs:
      how:
        type: choice
        options: [patch, minor, major]
        default: patch

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]" build twine
      - name: doctor gate (fail fast on missing prereqs)
        run: shipit-skill doctor
        env:
          PYPI_TOKEN: ${{{{ secrets.PYPI_TOKEN }}}}
      - name: run shipit-skill release
        run: >
          shipit-skill release --lang {lang} --pkg {pkg}
          --how ${{{{ inputs.how }}}} --repo ${{{{ github.repository }}}}
          --execute
        env:
          PYPI_TOKEN: ${{{{ secrets.PYPI_TOKEN }}}}
"""


def generate_release(lang: str, pkg: str) -> str:
    """Generate a release.yml workflow that runs `release --execute` manually."""
    return RELEASE_YML.format(lang=lang, pkg=pkg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["python", "typescript"])
    ap.add_argument("--server", help="MCP server console-script name (python only)")
    ap.add_argument("--pkg", default="app", help="Docker image / package name")
    ap.add_argument("--py-versions", default='"3.9", "3.12"', help="comma list")
    ap.add_argument("--base-py", default="3.9", help="base interpreter for extras-free install")
    ap.add_argument("--release", action="store_true", help="emit release.yml instead of ci.yml")
    args = ap.parse_args()

    if args.release:
        print(generate_release(args.lang, args.pkg))
        return

    print(generate_ci(
        args.lang,
        server=args.server,
        pkg=args.pkg,
        py_versions=args.py_versions,
        base_py=args.base_py,
    ))


if __name__ == "__main__":
    main()
