"""Tests for shipit_skill package modules and CLI."""

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def run_mod(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", f"shipit_skill.{module}", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "shipit_skill", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


# --- ci ---


def test_ci_python_yaml_valid():
    r = run_mod("ci", "--lang", "python", "--server", "zs-mcp", "--pkg", "app")
    assert r.returncode == 0
    import yaml

    data = yaml.safe_load(r.stdout)
    assert "test" in data["jobs"]
    assert "docker" in data["jobs"]
    assert "matrix" in data["jobs"]["test"]["strategy"]


def test_ci_python_without_server_has_no_docker_job():
    r = run_mod("ci", "--lang", "python")
    import yaml

    data = yaml.safe_load(r.stdout)
    assert "docker" not in data["jobs"]


def test_ci_typescript_yaml_valid():
    r = run_mod("ci", "--lang", "typescript")
    assert r.returncode == 0
    import yaml

    data = yaml.safe_load(r.stdout)
    assert "build" in data["jobs"]


# --- promo_check ---


def test_promo_check_detects_stale_version(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "# post\nInstall v0.1.0 and check PR #1234\n", encoding="utf-8"
    )
    r = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1", "--prs", "1234=open")
    assert r.returncode == 1
    assert "stale version 0.1.0" in r.stdout


def test_promo_check_ignores_ip_like_versions(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "proxy at 127.0.0.1:13579 and version 0.1.1\n", encoding="utf-8"
    )
    r = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1", "--no-links")
    assert r.returncode == 0


def test_promo_check_unknown_pr(tmp_path: Path):
    (tmp_path / "post.md").write_text("see PR #9999\n", encoding="utf-8")
    r = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1", "--no-links")
    assert r.returncode == 1
    assert "unknown PR/issue #9999" in r.stdout


def test_promo_check_broken_link(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "see https://github.com/skyzhao1223/definitely-not-a-repo-xyz\n", encoding="utf-8"
    )
    r = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1", "--prs", "")
    assert r.returncode == 1
    assert "broken link" in r.stdout


# --- mcp_smoke ---


def test_mcp_smoke_ok():
    payload = (
        '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x","version":"1"}}}\n'
        '{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"a"}]}}\n'
    )
    r = subprocess.run(
        [sys.executable, "-m", "shipit_skill.mcp_smoke"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert r.returncode == 0
    assert "initialize OK" in r.stdout


def test_mcp_smoke_fails_on_missing_tools():
    payload = '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x","version":"1"}}}\n'
    r = subprocess.run(
        [sys.executable, "-m", "shipit_skill.mcp_smoke"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert r.returncode != 0
    assert "tools/list" in r.stderr


# --- glama ---


def test_glama_reports_not_listed():
    r = run_mod("glama", "--repo", "skyzhao1223/definitely-not-a-repo-xyz")
    assert r.returncode == 1
    assert "NOT LISTED YET" in r.stdout


# --- CLI ---


def test_cli_init_scaffolds_project(tmp_path: Path):
    target = tmp_path / "hello-mcp"
    r = run_cli(
        "init",
        str(target),
        "--server",
        "hello-mcp",
        "--pkg",
        "hello-mcp",
    )
    assert r.returncode == 0, r.stderr
    assert (target / ".github/workflows/ci.yml").exists()
    assert (target / "Dockerfile").exists()
    assert (target / ".dockerignore").exists()
    assert (target / "scripts/mcp_smoke.py").exists()
    assert (target / "promo/README.md").exists()


def test_cli_ci_writes_file(tmp_path: Path):
    out = tmp_path / "ci.yml"
    r = run_cli("ci", "--lang", "python", "--write", str(out))
    assert r.returncode == 0
    assert out.exists()
    assert "name: CI" in out.read_text(encoding="utf-8")


def test_cli_publish_prints_commands():
    r = run_cli("publish", "--lang", "python", "--pkg", "demo")
    assert r.returncode == 0
    assert "twine upload" in r.stdout


# --- wheel contents ---


def test_wheel_contains_skill_and_package():
    wheels = list(DIST.glob("shipit_skill-*.whl"))
    if not wheels:
        import pytest

        pytest.skip("no built wheel in dist/ (run python -m build first)")
    wheel = max(wheels, key=lambda p: p.stat().st_mtime)
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
    assert any(n.endswith("shipit_skill/__init__.py") for n in names)
    assert any("shipit_skill/templates/Dockerfile" in n for n in names)
    assert any("shipit_skill/templates/promo/README.md" in n for n in names)
