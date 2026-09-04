---
name: shipit-skill
description: >-
  Ship a developer tool (AI agent tool, MCP server, CLI, or library) from
  "it works" to "published + listed + marketable" in one pass. Triggers on
  phrases like 上线 / 发布 / publish / release / 收录 / awesome PR / Glama /
  launch / 宣传 / promo, or when a repo has code+tests but no CI, no package
  release, no directory listing, or no promo material. Covers engineering
  baseline → publish → directory listing → promo across Python/PyPI and
  TypeScript/npm. Use whenever the goal is to take an existing open-source
  project and ship it properly.
---

# shipit-skill — one-pass launch pipeline for developer tools

Take an existing repo from "it works" to **published + listed + marketable**.
Four phases, each with a hard exit criterion. Skipping a phase is allowed only
if its exit criterion is already met.

> Philosophy: **look before you build.** Check what already exists and what the
> ecosystem requires *first* — the same way you'd advise any user not to
> reinvent a wheel.

---

## Phase 0 — Recon (30s, always)

Run these checks before touching anything:

1. **Existing repo state** — `git status`, `git remote -v`, recent `git log`.
2. **Package registration** — is the name taken? (`pip index versions <name>`,
   `npm view <name>`, registry CDN). Names collide often; scoped names for npm
   (`@org/pkg`) dodge typosquatting rules.
3. **Similar projects** — search GitHub for direct competitors. If one exists,
   note the differentiation explicitly; don't build a carbon copy.
4. **The "exit criteria" gaps** — CI? Dockerfile? GitHub Release? listed on
   Glama / awesome dirs? promo material current? Build a checklist of what's
   missing. That checklist drives the rest.

Output: a short gap report + plan. Get confirmation before Phase 1 if the
gaps are large.

---

## Phase 1 — Engineering baseline

Exit criterion: **CI green on the default branch**, package metadata correct,
Dockerfile present (if it's an MCP/CLI server).

- **CI**: add GitHub Actions. Python: matrix over supported versions, but mind
  extras that require a newer interpreter (e.g. `mcp>=2.0` needs py3.10+ — run
  the base on 3.9, extras on 3.12). Always include lint + tests + a
  **container MCP handshake** job if a server ships.
- **Dockerfile**: needed for Glama and container users. For stdio MCP servers:
  base image + install the package + `CMD [the-server-command]`. Build **from
  source** (COPY src) unless the published package is verified good — a stale
  PyPI/npm release will silently break introspection.
- **`.dockerignore`**: keep the image minimal (no `.git`, tests, promo, docs).
- **Version from metadata**: MCP `serverInfo.version` and CLI `--version` must
  read the package version, not a hardcoded string.
- **Dependency floor**: if your code targets a new SDK API, set the dependency
  floor (`mcp>=2.0`), don't leave `>=1.0` — pip/npm resolve to latest and break
  fresh installs.

Verify: clean `pip install .[extras]` / `npm install` in a temp venv, then run
the MCP handshake (`initialize` + `tools/list`) against the *container*.

---

## Phase 2 — Publish

Exit criterion: **package on the registry**, GitHub Release with tag + notes,
clean-env install verified.

- **Version bump** → build artifacts (`python -m build` / `npm pack`).
- **Tag + GitHub Release**: title `vX.Y.Z`, notes with Changes / Install /
  What-it-fixes. Let `gh release create` attach from the tag.
- **Registry publish**:
  - PyPI: needs a token (granular, scoped to the package, **Upload** perm).
    If the token is malformed PyPI returns `403 Invalid or non-existent
    authentication information` — UUID-style strings are wrong; real PyPI
    tokens start `pypi-`. `twine upload` with `--username __token__`.
  - npm: scoped names need the org to exist; granular token with bypass-2FA
    for automation; `--//registry.npmjs.org/:_authToken` inline avoids writing
    creds to disk.
- **Fresh-install verification** (non-negotiable): create a venv / clean dir,
  install from the *registry*, import the module / run the CLI / do the MCP
  handshake. This catches "works on my machine" packaging bugs.
- **Gotchas**:
  - npm CDN serves cached 404s for minutes after first publish — don't panic,
    cache-bust with a query param.
  - `File already exists` on retry usually means the first attempt succeeded.
  - Lockfile drift: rename packages → always `npm install` to regen the lock
    or `npm ci` fails in CI.

---

## Phase 3 — Directory listings

Exit criterion: **listed on Glama with a score badge** and **awesome PR open
(or merged)**.

- **Glama** (`glama.ai/mcp/servers`): user submits via browser (GitHub OAuth —
  cannot be automated). Before submitting: Dockerfile must exist and pass
  introspection (see Phase 1). After submit: the page takes **minutes to hours**
  to appear — poll `https://glama.ai/mcp/servers/<owner>/<repo>` and
  `/badges/score.svg`. Add the badge to the repo README once live:
  `[![owner/repo MCP server](https://glama.ai/mcp/servers/owner/repo/badges/score.svg)](https://glama.ai/mcp/servers/owner/repo)`
- **awesome-mcp-servers** (and similar curated lists): PRs are triaged by bots.
  Format per the list's current convention (badge + lang + scope + OS + install
  cmd). Maintainers now require the Glama badge in the entry — submit Glama
  *first*. Add `🤖🤖🤖` to the PR title to opt into the agent fast-track.
  Fork → branch off latest upstream main → add entry → PR. If a previous PR was
  closed for inactivity, force-push the branch or recreate it.
- **Other directories** (Smithery, PulseMCP, mcp.so…): Smithery reads a
  `smithery.yaml` at repo root (stdio start command + optional env schema).

---

## Phase 4 — Promo material

Exit criterion: **promo docs' versions/links/PR numbers match reality**; per-
platform posts are *ready to paste* (user posts manually — no fake automation).

- Maintain `promo/` with per-platform files (V2EX, 知乎, Reddit, X, community).
- **Freshness check** (run whenever versions/PRs change): grep promo files for
  old version numbers, dead PR links, stale release URLs. Update or mark stale.
- **Fact discipline**: verify every number/claim before posting — rerun the
  tool and compare output. Wrong claims get torn apart in comments (e.g. a
  "no LICENSE" claim that's actually a GitHub metadata quirk).
- Keep install commands unpinned (`pip install pkg`) so promo doesn't rot.

---

## Automation boundary

| Step | Who runs it |
|------|-------------|
| CI files, Dockerfile, metadata, code fixes | Agent |
| Build artifacts, fresh-install verification | Agent |
| Registry publish (PyPI/npm) | Agent, **with a user-supplied token** |
| Glama browser submit | User (OAuth) |
| awesome/other PR create | Agent |
| Posting to platforms | User |

Never fabricate credentials; ask for the token explicitly and use it inline,
never write it to a file.

## Real-world scars (from shipping wheel-hub + zspace-cli)

1. `mcp>=1.0` in extras + new SDK → fresh installs crash. Set floors.
2. Python 3.9 can't install `mcp>=2.0`; CI matrix must split base vs extras.
3. YAML block scalar + inline python heredoc = broken workflow. Use a script file.
4. MCP 2.x `Server` object has no `list_tools` — use `@server.tool()` decorators.
5. Glama introspection needs stdin held open for a beat (`sleep 1`) in smoke tests.
6. PyPI token formats: `pypi-...` real, UUID = wrong.
7. npm typosquatting blocks `wheel-hub` next to `wheelhub`; scoped names work.
8. `.dockerignore` missing → giant images / secrets in build context.
