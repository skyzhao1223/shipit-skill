# Example — shipping a minimal MCP server with ship-it

This walks the 4 phases against a toy `hello-mcp` server so you can see exactly
what ship-it produces at each step. Reproduce it locally to learn the pipeline,
then apply the same steps to your real project.

```
hello-mcp/                  # your project (already has working code)
├── pyproject.toml          # name=hello-mcp, extras mcp=["mcp>=2.0; python_version >= '3.10'"]
├── src/hello_mcp/          # server.py with @server.tool() handlers
├── tests/                  # passing tests
└── scripts/mcp_smoke.py    # copy from ship-it/scripts/mcp_smoke.py
```

## Phase 1 — Baseline

```bash
# generate CI (python server → includes Docker handshake job)
python3 ship-it/scripts/ci.py --lang python --server hello-mcp --pkg hello-mcp \
  > hello-mcp/.github/workflows/ci.yml

# Dockerfile (build from source so the image matches tested code)
cat > hello-mcp/Dockerfile <<'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir ".[mcp]"
CMD ["hello-mcp"]
EOF
cat > hello-mcp/.dockerignore <<'EOF'
.git
.github
tests/
dist/
EOF
```

Exit check: CI green, `docker build` passes, handshake OK:

```bash
cd hello-mcp
{ printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"s","version":"0"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'; sleep 1; } \
  | docker run --rm -i hello-mcp 2>/dev/null | python3 scripts/mcp_smoke.py
# → initialize OK ... / tools/list OK ...
```

## Phase 2 — Publish

```bash
python3 ship-it/scripts/publish.py --lang python --pkg hello-mcp --server hello-mcp --verify
# prints build + twine commands; PYPI_TOKEN=<pypi-...> twine upload dist/...
```

## Phase 3 — Listings

```bash
python3 ship-it/scripts/glama.py --repo <you>/hello-mcp --poll 6
# → LISTED ✅ once the build queue finishes (minutes to hours)

python3 ship-it/scripts/awesome_pr.py \
  --upstream punkpeye/awesome-mcp-servers \
  --repo <you>/hello-mcp --fork <you>/awesome-mcp-servers \
  --branch add-hello-mcp --title "Add <you>/hello-mcp to <Category>"
```

## Phase 4 — Promo

```bash
# keep promo/ with per-platform posts; when versions/PRs change:
python3 ship-it/scripts/promo_check.py --dir promo --version 0.1.0 --prs 1234=open
# → exit 1 lists every stale version / unknown PR before you paste anything
```

## Gotchas this example demonstrates

- `mcp>=2.0` needs Python 3.10+ → CI matrix splits base (3.9) vs extras (3.12).
- Dockerfile builds from `src/`, not the PyPI release → no stale-package surprises.
- Glama needs stdin held open (`sleep 1`) during the handshake smoke test.
- Promo versions rot fast → always run `promo_check.py` after a release.
