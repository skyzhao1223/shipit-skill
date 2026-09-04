#!/usr/bin/env python3
"""Generate a CI workflow for a Python or TypeScript project.

Usage:
    python3 scripts/ci.py --lang python  [--server zs-mcp]  [--pkg zspace-cli]
    python3 scripts/ci.py --lang typescript

Prints the YAML to stdout. Pipe to .github/workflows/ci.yml.
"""

# ruff: noqa: E501
import argparse

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["python", "typescript"])
    ap.add_argument("--server", help="MCP server console-script name (python only)")
    ap.add_argument("--pkg", default="app", help="Docker image / package name")
    ap.add_argument("--py-versions", default='"3.9", "3.12"', help="comma list")
    ap.add_argument("--base-py", default="3.9", help="base interpreter for extras-free install")
    args = ap.parse_args()

    if args.lang == "typescript":
        print(TS_CI)
        return

    server_block = ""
    if args.server:
        server_block = PY_SERVER_BLOCK.format(pkg=args.pkg)
    print(PY_CI.format(
        py_versions=args.py_versions,
        base_py=args.base_py,
        server_block=server_block,
    ))


if __name__ == "__main__":
    main()
