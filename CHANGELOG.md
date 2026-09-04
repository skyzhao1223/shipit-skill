# Changelog

## [0.7.0] - 2026-09-04

Bumped from 0.6.0.

## [0.6.0] - 2026-09-04

Bumped from 0.5.0.

## [0.5.0] - 2026-09-04

Bumped from 0.4.0.

## [0.4.0] - 2026-09-04

Bumped from 0.3.1.

## [0.3.1] - 2026-09-04

Bumped from 0.3.0.

## [0.3.0] - 2026-09-04

### Added

- **`shipit-skill preflight`** — launch-readiness gap report: scans a repo for
  CI / Dockerfile / .dockerignore / git remote / promo / version consistency
  and prints ✓/✗ per check (offline by default, `--online` adds GitHub release).
- **`shipit-skill bump patch|minor|major|set:X.Y.Z`** — semantic version bump that
  syncs pyproject.toml, `__init__.__version__`, and CHANGELOG.md. `--dry-run` to preview.
  *(Fixes a minor-bump bug: `0.1.0` minor now yields `0.2.0`, not `2.0`.)*
- **`shipit-skill release`** — one-step recipe: bump → build → git tag/push →
  GitHub Release (`--repo`) → publish commands → promo check. `--dry-run` to preview.
- **`action.yml`** — reusable GitHub composite action
  (`uses: skyzhao1223/shipit-skill@v1` with `command`/`args`/`pkg`/`repo` inputs).
- **Interactive `init`** — prompts for missing `--server`/`--pkg`; `--force` to
  overwrite existing files, `--dry-run` to preview.
- **Type checking**: `pyright` job in CI + `[tool.pyright]` config (basic mode,
  Python 3.9 target).
- **Pre-commit**: `.pre-commit-config.yaml` with ruff + actionlint.
- **Multi-OS CI**: matrix on `ubuntu-latest / macos-latest / windows-latest`
  × Python 3.9 / 3.12, plus separate typecheck and actionlint jobs.
- **Tests**: 14 → 19 (preflight gap/ok, bump dry-run/write, release recipe).

## [0.2.0] - 2026-09-04

### Added — shipit-skill is now a real Python package + CLI

- **`shipit_skill` package** — scripts moved from `scripts/` into an importable
  package (`ci`, `publish`, `glama`, `mcp_smoke`, `promo_check`, `awesome_pr`).
- **CLI**: `pip install shipit-skill` → `shipit-skill init|ci|publish|check-promo|check-glama|awesome-pr`.
- **`shipit-skill init`** scaffold: generates CI / Dockerfile / .dockerignore /
  mcp_smoke.py / promo skeleton in one command.
- **`promo_check` HTTP link check**: broken GitHub URLs are now detected, not
  just stale versions / unknown PRs.
- **Tests**: 14 cases (was 9) — added `cli init`, `ci --write`, `publish`,
  broken-link, and wheel-content coverage.

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
