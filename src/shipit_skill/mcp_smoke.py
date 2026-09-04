"""MCP smoke test — read initialize + tools/list over stdio and assert basics.

CLI:
    printf '<init>\n<notify>\n<tools-list>\n' | <server-cmd> | python -m shipit_skill.mcp_smoke

Exits 0 if initialize and tools/list were both received and parseable.
"""

from __future__ import annotations

import json
import sys


def run_smoke(stream: object = None) -> bool:
    """Parse MCP stdio responses and assert initialize + tools/list arrived."""
    lines = stream if stream is not None else sys.stdin
    seen_init = False
    seen_tools = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id") == 1 and "result" in d:
            assert "serverInfo" in d["result"], d
            print("initialize OK:", d["result"]["serverInfo"])
            seen_init = True
        if d.get("id") == 2 and "result" in d:
            names = [t["name"] for t in d["result"]["tools"]]
            print("tools/list OK:", len(names), "tools:", names[:4], "...")
            seen_tools = True
    if not seen_init:
        raise AssertionError("no initialize response received")
    if not seen_tools:
        raise AssertionError("no tools/list response received")
    return True


def main() -> None:
    try:
        run_smoke()
    except AssertionError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
