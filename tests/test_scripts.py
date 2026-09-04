"""Tests for shipit-skill helper scripts."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_ci_python_yaml_valid():
    r = run_script("ci.py", "--lang", "python", "--server", "zs-mcp", "--pkg", "app")
    assert r.returncode == 0
    import yaml

    data = yaml.safe_load(r.stdout)
    assert "test" in data["jobs"]
    assert "docker" in data["jobs"]
    assert "matrix" in data["jobs"]["test"]["strategy"]


def test_ci_python_without_server_has_no_docker_job():
    r = run_script("ci.py", "--lang", "python")
    import yaml

    data = yaml.safe_load(r.stdout)
    assert "docker" not in data["jobs"]


def test_ci_typescript_yaml_valid():
    r = run_script("ci.py", "--lang", "typescript")
    assert r.returncode == 0
    import yaml

    data = yaml.safe_load(r.stdout)
    assert "build" in data["jobs"]


def test_promo_check_detects_stale_version(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "# post\nInstall v0.1.0 and check PR #1234\n", encoding="utf-8"
    )
    r = run_script(
        "promo_check.py", "--dir", str(tmp_path), "--version", "0.1.1", "--prs", "1234=open"
    )
    assert r.returncode == 1
    assert "stale version 0.1.0" in r.stdout


def test_promo_check_ignores_ip_like_versions(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "proxy at 127.0.0.1:13579 and version 0.1.1\n", encoding="utf-8"
    )
    r = run_script("promo_check.py", "--dir", str(tmp_path), "--version", "0.1.1")
    assert r.returncode == 0


def test_promo_check_unknown_pr(tmp_path: Path):
    (tmp_path / "post.md").write_text("see PR #9999\n", encoding="utf-8")
    r = run_script("promo_check.py", "--dir", str(tmp_path), "--version", "0.1.1")
    assert r.returncode == 1
    assert "unknown PR/issue #9999" in r.stdout


def test_mcp_smoke_ok():
    payload = (
        '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x","version":"1"}}}\n'
        '{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"a"}]}}\n'
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "mcp_smoke.py")],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "initialize OK" in r.stdout


def test_mcp_smoke_fails_on_missing_tools():
    payload = '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x","version":"1"}}}\n'
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "mcp_smoke.py")],
        input=payload,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
    assert "tools/list" in r.stderr


def test_glama_reports_not_listed():
    # glama.py with a repo guaranteed to not be listed should exit 1.
    r = run_script("glama.py", "--repo", "skyzhao1223/definitely-not-a-repo-xyz")
    assert r.returncode == 1
    assert "NOT LISTED YET" in r.stdout
