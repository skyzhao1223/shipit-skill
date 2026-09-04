# ⚙️ shipit-skill

[![CI](https://github.com/skyzhao1223/shipit-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/skyzhao1223/shipit-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Take an existing developer tool from "it works" to "published + listed + marketable" — one pass.**

`shipit-skill` is an Agent Skill that runs the full launch pipeline for AI/developer tools
(MCP servers, CLIs, libraries): engineering baseline → publish → directory listings →
promo material. It was distilled from shipping [wheel-hub](https://github.com/skyzhao1223/wheel-hub),
[zspace-cli](https://github.com/skyzhao1223/zspace-cli) and
[media-manager-skill](https://github.com/skyzhao1223/media-manager-skill) — every gotcha
below is one that actually bit during those releases.

## Install

Copy this folder into your project (or your agent's skills dir):

```bash
# for the current project
cp -r shipit-skill/ ~/your-project/.opencode/skills/shipit-skill   # opencode
# cp -r shipit-skill/ ~/your-project/skills/shipit-skill            # Claude Code, Cursor, etc.
```

## What it does

| Phase | Exit criterion | Scripts |
|-------|----------------|---------|
| **0. Recon** | gap report (CI? Docker? Release? listed? promo?) | — |
| **1. Baseline** | CI green, metadata right, Dockerfile present | `scripts/ci.py`, `scripts/mcp_smoke.py` |
| **2. Publish** | on registry + GitHub Release + clean-env verified | `scripts/publish.py` |
| **3. Listings** | Glama live + awesome PR open | `scripts/glama.py`, `scripts/awesome_pr.py` |
| **4. Promo** | promo docs match reality | `scripts/promo_check.py` |

See [`SKILL.md`](SKILL.md) for the full agent instructions and the automation
boundary (what the agent runs vs. what needs a human/credential).

## Example

[`examples/mcp-server-launch.md`](examples/mcp-server-launch.md) walks all four
phases against a toy `hello-mcp` server — reproduce it locally to learn the
pipeline before applying it to a real project.

## Development

```bash
pip install -e ".[dev]"
pytest -q          # 9 tests
ruff check .       # lint
```

## The scars (why this exists)

- `mcp>=1.0` + a new SDK → fresh installs crash. Set dependency floors.
- Python 3.9 can't install `mcp>=2.0` — split the CI matrix.
- YAML block scalar + inline heredoc = broken workflow. Use a script file.
- Glama introspection needs stdin held open (`sleep 1`) in smoke tests.
- PyPI tokens start `pypi-`; UUID-style strings are wrong and 403.
- npm typosquatting blocks similar names — scoped names dodge it.
- Glama builds take minutes to hours — poll, don't panic.

## License

MIT
