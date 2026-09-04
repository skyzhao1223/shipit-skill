#!/usr/bin/env python3
"""MCP smoke test: read initialize + tools/list over stdio and assert basics.

Usage:
    printf '<init-json>\n<notify-json>\n<tools-list-json>\n' | <server-cmd> | python3 scripts/mcp_smoke.py

Exits 0 if initialize and tools/list were both received and parseable.
"""

import json
import sys


def main() -> None:
    seen_init = False
    seen_tools = False
    for line in sys.stdin:
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
    assert seen_init, "no initialize response received"
    assert seen_tools, "no tools/list response received"


if __name__ == "__main__":
    main()
