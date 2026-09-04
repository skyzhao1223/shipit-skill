# Changelog

## [0.1.0] - 2026-09-04

Initial release.

### Added

- **SKILL.md** — one-pass launch pipeline for developer tools: Phase 0 recon,
  Phase 1 engineering baseline, Phase 2 publish, Phase 3 directory listings,
  Phase 4 promo. Includes an automation boundary and a "real-world scars"
  gotcha list.
- **scripts/**
  - `ci.py` — CI workflow generator (Python with optional MCP-server Docker
    handshake job, TypeScript).
  - `publish.py` — prints build + registry publish commands, runs fresh-install
    verification.
  - `glama.py` — Glama listing/badge check with optional polling.
  - `awesome_pr.py` — recipe for submitting to awesome directories (fork,
    branch, Glama-badge entry, PR).
  - `promo_check.py` — promo freshness check (stale versions / unknown PRs),
    ignores IP-like version fragments.
  - `mcp_smoke.py` — MCP initialize + tools/list smoke test over stdio.
- **tests/** — 9 pytest cases covering the scripts.
- **examples/mcp-server-launch.md** — end-to-end walkthrough using a toy MCP
  server.
- **pyproject.toml** — dev toolchain (pytest, ruff).
- **.github/workflows/ci.yml** — lint + test.
- **README.md**, **MIT LICENSE**.
