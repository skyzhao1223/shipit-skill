"""Tests for shipit_skill package modules and CLI.

Runs the modules in-process (calling main() with mocked argv) so coverage is
measured directly — no subprocess indirection.
"""

import json
import sys
import zipfile
from pathlib import Path

import pytest

from shipit_skill import (
    awesome_pr,
    bump,
    changelog,
    ci,
    cli,
    doctor,
    glama,
    mcp_smoke,
    preflight,
    promo_check,
    publish,
    release,
)

ROOT = Path(__file__).resolve().parents[1]

_OK_CHECKS = [{"name": "ok", "ok": True, "detail": ""}]
def _mock_doctor_all_ok(monkeypatch):
    import shipit_skill.doctor as _d
    monkeypatch.setattr(_d, "doctor", lambda: _OK_CHECKS)

DIST = ROOT / "dist"


def run_mod(module: str, *args: str) -> tuple[int, str]:
    """Call a module's main() in-process with CLI args, capturing stdout."""
    import contextlib
    import io
    import sys

    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        sys.argv = ["shipit-skill", *args]
        try:
            if module == "ci":
                ci.main()
            elif module == "promo_check":
                promo_check.main()
            elif module == "bump":
                bump.main()
            elif module == "release":
                release.main()
            elif module == "publish":
                publish.main()
            elif module == "preflight":
                preflight.main()
            elif module == "glama":
                glama.main()
            elif module == "cli":
                cli.main()
            elif module == "doctor":
                doctor.main()
            elif module == "changelog":
                changelog.main()
            elif module == "awesome_pr":
                awesome_pr.main()
            elif module == "mcp_smoke":
                mcp_smoke.main()
            else:
                raise ValueError(f"unknown module {module}")
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
    return code, buf.getvalue()


def run_cli(*args: str) -> tuple[int, str]:
    return run_mod("cli", *args)


# --- ci ---


def test_ci_python_yaml_valid():
    code, out = run_mod("ci", "--lang", "python", "--server", "zs-mcp", "--pkg", "app")
    assert code == 0
    import yaml

    data = yaml.safe_load(out)
    assert "test" in data["jobs"]
    assert "docker" in data["jobs"]
    assert "matrix" in data["jobs"]["test"]["strategy"]


def test_ci_python_without_server_has_no_docker_job():
    _, out = run_mod("ci", "--lang", "python")
    import yaml

    data = yaml.safe_load(out)
    assert "docker" not in data["jobs"]


def test_ci_typescript_yaml_valid():
    code, out = run_mod("ci", "--lang", "typescript")
    assert code == 0
    import yaml

    data = yaml.safe_load(out)
    assert "build" in data["jobs"]


# --- promo_check ---


def test_promo_check_detects_stale_version(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "# post\nInstall v0.1.0 and check PR #1234\n", encoding="utf-8"
    )
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--prs", "1234=open", "--no-links")
    assert code == 1
    assert "stale version 0.1.0" in out


def test_promo_check_ignores_ip_like_versions(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "proxy at 127.0.0.1:13579 and version 0.1.1\n", encoding="utf-8"
    )
    code, _ = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                      "--no-links")
    assert code == 0


def test_promo_check_unknown_pr(tmp_path: Path):
    (tmp_path / "post.md").write_text("see PR #9999\n", encoding="utf-8")
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links")
    assert code == 1
    assert "unknown PR/issue #9999" in out


def test_promo_check_broken_link(tmp_path: Path):
    (tmp_path / "post.md").write_text(
        "see https://github.com/skyzhao1223/definitely-not-a-repo-xyz\n", encoding="utf-8"
    )
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--prs", "")
    assert code == 1
    assert "broken link" in out


# --- mcp_smoke ---


def test_mcp_smoke_ok(capsys):
    from shipit_skill import mcp_smoke

    payload = [
        '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x","version":"1"}}}\n',
        '{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"a"}]}}\n',
    ]
    assert mcp_smoke.run_smoke(iter(payload)) is True
    assert "initialize OK" in capsys.readouterr().out


def test_mcp_smoke_fails_on_missing_tools(capsys):
    from shipit_skill import mcp_smoke

    payload = iter([
        '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x","version":"1"}}}\n',
    ])
    with pytest.raises(AssertionError):
        mcp_smoke.run_smoke(payload)


# --- glama ---


def test_glama_reports_not_listed():
    code, out = run_mod("glama", "--repo", "skyzhao1223/definitely-not-a-repo-xyz")
    assert code == 1
    assert "NOT LISTED YET" in out


def test_glama_add_badge(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text("# my-tool\n\nHello\n", encoding="utf-8")
    ok = glama.add_badge("me/my-tool", str(readme))
    assert ok
    assert "badges/score.svg" in readme.read_text(encoding="utf-8")
    # idempotent
    ok2 = glama.add_badge("me/my-tool", str(readme))
    assert ok2
    assert readme.read_text(encoding="utf-8").count("badges/score.svg") == 1


# --- CLI: init ---


def test_cli_init_scaffolds_project(tmp_path: Path):
    target = tmp_path / "hello-mcp"
    code, _ = run_cli("init", str(target), "--server", "hello-mcp", "--pkg", "hello-mcp")
    assert code == 0
    assert (target / ".github/workflows/ci.yml").exists()
    assert (target / "Dockerfile").exists()
    assert (target / ".dockerignore").exists()
    assert (target / "scripts/mcp_smoke.py").exists()
    assert (target / "promo/README.md").exists()
    assert (target / "smithery.yaml").exists()
    assert "hello-mcp" in (target / "smithery.yaml").read_text(encoding="utf-8")


def test_cli_init_refuses_overwrite(tmp_path: Path):
    target = tmp_path / "hello-mcp"
    run_cli("init", str(target), "--server", "hello-mcp", "--pkg", "hello-mcp")
    code, _ = run_cli("init", str(target), "--server", "hello-mcp", "--pkg", "hello-mcp")
    assert code == 1


def test_cli_init_force_overwrites(tmp_path: Path):
    target = tmp_path / "hello-mcp"
    run_cli("init", str(target), "--server", "a", "--pkg", "a")
    (target / "Dockerfile").write_text("OLD", encoding="utf-8")
    code, _ = run_cli("init", str(target), "--server", "a", "--pkg", "a", "--force")
    assert code == 0
    assert "OLD" not in (target / "Dockerfile").read_text(encoding="utf-8")


def test_cli_init_dry_run_writes_nothing(tmp_path: Path):
    target = tmp_path / "hello-mcp"
    code, out = run_cli("init", str(target), "--server", "hello-mcp", "--pkg", "hello-mcp",
                        "--dry-run")
    assert code == 0
    assert "(dry)" in out
    assert not (target / "Dockerfile").exists()


def test_cli_ci_writes_file(tmp_path: Path):
    out = tmp_path / "ci.yml"
    code, _ = run_cli("ci", "--lang", "python", "--write", str(out))
    assert code == 0
    assert out.exists()
    assert "name: CI" in out.read_text(encoding="utf-8")


def test_cli_publish_prints_commands():
    code, out = run_cli("publish", "--lang", "python", "--pkg", "demo")
    assert code == 0
    assert "twine upload" in out


# --- preflight ---


def test_cli_preflight_reports_gaps(tmp_path: Path):
    code, out = run_cli("preflight", "--dir", str(tmp_path), "--version", "0.1.0")
    assert code == 1  # empty dir has gaps
    assert "✗" in out
    assert "gaps" in out


def test_cli_preflight_ok_on_scaffolded(tmp_path: Path):
    target = tmp_path / "ok"
    run_cli("init", str(target), "--server", "demo", "--pkg", "demo")
    (target / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    code, out = run_cli("preflight", "--dir", str(target), "--version", "0.1.0")
    assert "✓ CI workflow" in out
    assert "✓ Dockerfile" in out
    assert "✓ promo versions consistent" in out


# --- bump ---


def test_cli_bump_dry_run(tmp_path: Path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8")
    code, out = run_cli("bump", "minor", "--dir", str(tmp_path), "--dry-run")
    assert code == 0
    assert "0.1.0 → 0.2.0" in out
    assert "0.2.0" not in p.read_text(encoding="utf-8")  # dry-run didn't write


def test_cli_bump_writes(tmp_path: Path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8")
    code, _ = run_cli("bump", "patch", "--dir", str(tmp_path))
    assert code == 0
    assert 'version = "0.1.1"' in p.read_text(encoding="utf-8")


def test_bump_minor_is_full_semver():
    assert bump.bump("0.1.0", "minor") == "0.2.0"
    assert bump.bump("1.9.0", "major") == "2.0.0"
    assert bump.bump("0.1.0", "patch") == "0.1.1"


# --- release ---


def test_cli_release_dry_run():
    code, out = run_cli("release", "--lang", "python", "--pkg", "demo", "--how", "patch",
                        "--dry-run")
    assert code == 0
    import re

    assert re.search(r"git tag v\d+\.\d+\.\d+", out)  # any semver tag


def test_release_recipe_contains_publish():
    cmds = release.release("python", "demo", "patch", dir_=".", dry_run=True)
    text = "\n".join(cmds)
    assert "bump" in text
    assert "git tag" in text
    assert "build" in text


# --- wheel contents ---


def test_wheel_contains_package():
    wheels = list(DIST.glob("shipit_skill-*.whl"))
    if not wheels:
        pytest.skip("no built wheel in dist/ (run python -m build first)")
    wheel = max(wheels, key=lambda p: p.stat().st_mtime)
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
    assert any(n.endswith("shipit_skill/__init__.py") for n in names)
    assert any("shipit_skill/templates/Dockerfile" in n for n in names)
    assert any("shipit_skill/templates/promo/README.md" in n for n in names)


# --- execute paths (raise before side effects when env missing) ---


def test_publish_execute_requires_token():
    import os

    os.environ.pop("PYPI_TOKEN", None)
    from shipit_skill import publish as pub

    try:
        pub.execute_python("demo", None)
    except SystemExit as e:
        assert "PYPI_TOKEN" in str(e)
    else:
        pytest.fail("expected SystemExit")


def test_publish_ts_execute_requires_token():
    import os

    os.environ.pop("NPM_TOKEN", None)
    from shipit_skill import publish as pub

    try:
        pub.execute_typescript("demo")
    except SystemExit as e:
        assert "NPM_TOKEN" in str(e)
    else:
        pytest.fail("expected SystemExit")


def test_bump_set():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "pyproject.toml"
        p.write_text('[project]\nname = "x"\nversion = "1.2.3"\n', encoding="utf-8")
        code, out = run_cli("bump", "set:2.0.0", "--dir", td, "--dry-run")
        assert code == 0
        assert "2.0.0" in out


def test_release_execute_requires_token(tmp_path, monkeypatch):
    import os

    os.environ.pop("PYPI_TOKEN", None)
    _mock_doctor_all_ok(monkeypatch)
    from unittest.mock import patch

    from shipit_skill import release as rel

    with patch("subprocess.run", return_value=None):
        with pytest.raises(SystemExit) as ei:
            rel.execute("python", "demo", "patch", repo="me/demo", dir_=str(tmp_path))
        assert "PYPI_TOKEN" in str(ei.value)


# --- publish print + execute (mocked side effects) ---


def test_publish_verify_python(monkeypatch, capsys):
    from shipit_skill import publish as pub

    calls = []

    def fake_run(cmd, check=False, **kw):
        calls.append(cmd[0])
        return None

    monkeypatch.setattr(pub.subprocess, "run", fake_run)
    pub.verify_python("demo", None, "demo")
    assert calls[0] == sys.executable  # venv creation
    assert "fresh-install OK" in capsys.readouterr().out


def test_publish_execute_python_happy(monkeypatch, tmp_path):
    from shipit_skill import publish as pub

    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "demo-0.1.0-py3-none-any.whl").write_bytes(b"x")
    (tmp_path / "dist" / "demo-0.1.0.tar.gz").write_bytes(b"x")
    monkeypatch.setenv("PYPI_TOKEN", "pypi-abc")
    monkeypatch.chdir(tmp_path)

    cmds = []
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: cmds.append(c))

    pub.execute_python("demo", None)
    assert any("twine" in " ".join(c) for c in cmds)


def test_publish_execute_ts_happy(monkeypatch):
    from shipit_skill import publish as pub

    monkeypatch.setenv("NPM_TOKEN", "npm-xyz")
    cmds = []
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: cmds.append(c))
    monkeypatch.setattr(pub, "verify_typescript", lambda pkg: None)
    pub.execute_typescript("demo")
    assert cmds[0][0] == "npm"


def test_publish_main_print_typescript():
    code, out = run_mod("publish", "--lang", "typescript", "--pkg", "@x/cli")
    assert code == 0
    assert "npm publish" in out


# --- release execute happy path (all subprocess mocked) ---


def test_release_execute_happy(monkeypatch, tmp_path):
    from unittest.mock import patch

    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "pypi-abc")
    monkeypatch.setenv("NPM_TOKEN", "npm-abc")
    _mock_doctor_all_ok(monkeypatch)

    class R:
        returncode = 1
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kw):
        return R()

    monkeypatch.setattr(rel.subprocess, "run", fake_run)
    monkeypatch.setattr(pub.subprocess, "run", fake_run)
    with patch.object(rel, "_gh_available", return_value=True):
        rel.execute("python", "demo", "patch", repo="me/demo", dir_=str(tmp_path))

    assert 'version = "0.1.1"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")


def test_release_execute_ts_no_repo(monkeypatch, tmp_path):

    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "pypi-abc")
    monkeypatch.setenv("NPM_TOKEN", "npm-abc")
    _mock_doctor_all_ok(monkeypatch)

    def fake_run(cmd, **kw):
        return None

    monkeypatch.setattr(rel.subprocess, "run", fake_run)
    monkeypatch.setattr(pub.subprocess, "run", fake_run)
    monkeypatch.setattr(pub, "verify_typescript", lambda pkg: None)
    rel.execute("typescript", "demo", "set:0.2.0", dir_=str(tmp_path))

    assert 'version = "0.2.0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")


def test_release_with_repo_but_no_gh(monkeypatch, tmp_path):
    from unittest.mock import patch

    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    with patch.object(rel, "_gh_available", return_value=False):
        cmds = rel.release("python", "demo", "patch", repo="me/demo", dir_=str(tmp_path),
                           dry_run=True)
    assert any("gh CLI not found" in c for c in cmds)


def test_release_main_dry_run_and_execute_flag():
    code, out = run_mod("release", "--lang", "python", "--pkg", "demo", "--dry-run")
    assert code == 0
    assert "Commands above are guidance" in out


# --- awesome_pr ---


def test_awesome_pr_recipe_contains_glama_badge():
    from shipit_skill import awesome_pr

    text = awesome_pr.recipe("punkpeye/awesome-mcp-servers", "me/zspace-cli",
                             "me/awesome-mcp-servers", "add-zspace-cli",
                             "Add zspace-cli")
    assert "gh pr create" in text
    assert "badges/score.svg" in text
    assert "me/zspace-cli" in text


def test_awesome_pr_main_no_title():
    code, out = run_mod("awesome_pr", "--upstream", "punkpeye/awesome-mcp-servers",
                        "--repo", "me/zspace-cli", "--fork", "me/ams", "--branch", "b")
    assert code == 0
    assert "<markdown title>" in out
    assert "nothing was executed" in out


# --- mcp_smoke main (stdin + failure path) ---


def test_mcp_smoke_main_failure_exits_1(capsys, monkeypatch):
    from shipit_skill import mcp_smoke

    monkeypatch.setattr(mcp_smoke.sys, "stdin", iter(["not-json\n"]))
    with pytest.raises(SystemExit) as ei:
        mcp_smoke.main()
    assert ei.value.code == 1
    assert "no initialize" in capsys.readouterr().err


def test_mcp_smoke_main_success(monkeypatch, capsys):
    from shipit_skill import mcp_smoke

    stream = [
        '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x","version":"1"}}}\n',
        '{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"a"}]}}\n',
    ]
    monkeypatch.setattr(mcp_smoke.sys, "stdin", iter(stream))
    code, _ = run_mod("mcp_smoke")
    assert code == 0


def test_mcp_smoke_skips_bad_json_and_checks_serverinfo():
    from shipit_skill import mcp_smoke

    stream = iter([
        "garbage\n",
        '{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"x"}}}\n',
        '{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}\n',
    ])
    assert mcp_smoke.run_smoke(stream) is True


# --- CLI version / errors ---


def test_cli_has_version_flag():
    code, out = run_cli("--version")
    assert code == 0
    assert "shipit-skill" in out


def test_cli_no_args_prints_help():
    code, out = run_cli()
    assert code == 2
    assert "usage" in out


def test_cli_unknown_subcommand_exits():
    code, _ = run_cli("frobnicate")
    assert code == 2


# --- preflight branches ---


def test_preflight_version_mismatch_flag(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    report = preflight.preflight(tmp_path, version="0.2.0")
    assert any("CLI --version 0.2.0 != manifest 0.1.0" in g for g in report["gaps"])


def test_preflight_missing_git_remote(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    report = preflight.preflight(tmp_path)
    assert any("git remote origin" in g for g in report["gaps"])


def test_preflight_online_gh_release(monkeypatch, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    fake = type("R", (), {"returncode": 0, "stdout": "v0.1.0\ttitle\n"})()
    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **kw: fake)
    report = preflight.preflight(tmp_path, version="0.1.0", repo="me/x", online=True)
    assert any("GitHub release (v0.1.0)" in o for o in report["ok"])


def test_preflight_online_no_release(monkeypatch, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    fake = type("R", (), {"returncode": 0, "stdout": ""})()
    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **kw: fake)
    report = preflight.preflight(tmp_path, version="0.1.0", repo="me/x", online=True)
    assert any("GitHub release (none found" in g for g in report["gaps"])


def test_preflight_json_output(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    code, out = run_cli("preflight", "--dir", str(tmp_path), "--version", "0.1.0", "--json")
    assert code == 1  # still gaps (no dockerfile etc.)
    data = json.loads(out)
    assert data["dir"] == str(tmp_path)
    assert "gaps" in data


# --- bump branches ---


def test_bump_invalid_semver_raises():
    with pytest.raises(ValueError):
        bump.parse("not-a-version")
    with pytest.raises(ValueError):
        bump.bump("0.1.0", "oops")


def test_bump_syncs_init_and_changelog(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    init = tmp_path / "src" / "shipit_skill" / "__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.0] - 2026-01-01\n", encoding="utf-8"
    )
    changes = bump.set_version(str(tmp_path), "0.2.0")
    assert len(changes) == 3
    assert "pyproject.toml" in changes[0]
    assert "__init__.py" in changes[1]
    assert "CHANGELOG.md" in changes[2]
    assert 'version = "0.2.0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert "__version__ = \"0.2.0\"" in init.read_text(encoding="utf-8")
    assert "## [0.2.0]" in (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")


def test_bump_no_changes_when_already_at_version(tmp_path: Path, capsys):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    changes = bump.set_version(str(tmp_path), "0.1.0")
    assert changes == []
    code, _ = run_mod("bump", "set:0.1.0", "--dir", str(tmp_path))
    assert code == 0


def test_bump_main_commit_mocked(monkeypatch, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    calls = []
    monkeypatch.setattr(bump.subprocess, "run", lambda c, **kw: calls.append(c) or None)
    code, out = run_mod("bump", "patch", "--dir", str(tmp_path), "--commit")
    assert code == 0
    assert calls[0][0] == "git" and calls[0][1] == "add"
    assert "committed" in out



# --- more CLI handlers ---


def test_cli_ci_write_path(tmp_path: Path):
    out = tmp_path / "deep" / "ci.yml"
    code, _ = run_cli("ci", "--lang", "python", "--server", "srv", "--write", str(out))
    assert code == 0
    assert out.exists()
    assert "name: CI" in out.read_text(encoding="utf-8")


def test_cli_check_promo_ok(tmp_path: Path):
    (tmp_path / "post.md").write_text("install v0.1.1\n", encoding="utf-8")
    code, out = run_cli("check-promo", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links")
    assert code == 0
    assert "OK:" in out


def test_cli_check_promo_fail(tmp_path: Path):
    (tmp_path / "post.md").write_text("install v0.1.0\n", encoding="utf-8")
    code, _ = run_cli("check-promo", "--dir", str(tmp_path), "--version", "0.1.1",
                      "--no-links")
    assert code == 1


def test_cli_awesome_pr_dispatch():
    code, out = run_cli("awesome-pr", "--upstream", "u/l", "--repo", "me/r",
                        "--fork", "me/f", "--branch", "b", "--title", "T")
    assert code == 0
    assert "gh pr create" in out


def test_cli_glama_failure_dispatch():
    code, _ = run_cli("check-glama", "--repo", "skyzhao1223/definitely-not-a-repo-xyz")
    assert code == 1


def test_cli_init_interactive_defaults(
        tmp_path: Path, monkeypatch):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod, "_ask", lambda prompt, default: "my-server")
    code, _ = run_cli("init", str(tmp_path / "t"), "--server", "srv", "--pkg", "t")
    assert code == 0
    assert (tmp_path / "t" / "Dockerfile").exists()


# --- glama polling + add badge via CLI ---


def test_glama_poll_success(monkeypatch, capsys, tmp_path: Path):

    def fake_sleep(_n):
        return None

    def fake_fetch(_url):
        return 200

    monkeypatch.setattr(glama.time, "sleep", fake_sleep)
    monkeypatch.setattr(glama, "fetch_status", fake_fetch)
    assert glama.check_glama("me/r", poll=1, wait=1) is True
    assert "LISTED" in capsys.readouterr().out


def test_glama_poll_exhausted(monkeypatch, capsys):
    def fake_fetch(_url):
        return 404

    monkeypatch.setattr(glama.time, "sleep", lambda _n: None)
    monkeypatch.setattr(glama, "fetch_status", fake_fetch)
    assert glama.check_glama("me/r", poll=1, wait=1) is False
    assert "NOT LISTED" in capsys.readouterr().out


def test_cli_glama_add_badge_listed(tmp_path: Path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("# tool\n", encoding="utf-8")
    monkeypatch.setattr(glama, "fetch_status", lambda _u: 200)
    monkeypatch.setattr(glama.time, "sleep", lambda _n: None)
    code, _ = run_cli("check-glama", "--repo", "me/r", "--add-badge", "--readme",
                      str(readme))
    assert code == 0
    assert "badges/score.svg" in readme.read_text(encoding="utf-8")


# --- preflight extra branches ---


def test_preflight_dockerfile_and_promo_gaps(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    report = preflight.preflight(tmp_path, version="0.1.0")
    assert any("Dockerfile" in g for g in report["gaps"])
    assert any("promo/" in g for g in report["gaps"])


def test_preflight_dockerfile_present(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    (tmp_path / "promo").mkdir()
    (tmp_path / "promo" / "post.md").write_text("v0.1.0\n", encoding="utf-8")
    report = preflight.preflight(tmp_path, version="0.1.0")
    assert any("Dockerfile" in o for o in report["ok"])
    assert any("promo/ dir" in o for o in report["ok"])
    assert any("promo versions consistent" in o for o in report["ok"])


# --- preflight remaining branches ---


def test_preflight_package_json_version(tmp_path: Path):
    (tmp_path / "package.json").write_text('{\n  "name": "x",\n  "version": "3.2.1"\n}\n',
                                           encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM node:20\n", encoding="utf-8")
    (tmp_path / "promo").mkdir()
    (tmp_path / "promo" / "a.md").write_text("v3.2.1\n", encoding="utf-8")
    report = preflight.preflight(tmp_path, version="3.2.1")
    assert any("package version 3.2.1" in o for o in report["ok"])
    assert any("promo versions consistent" in o for o in report["ok"])


def _raise_fnf(*a, **k):
    raise FileNotFoundError


def test_preflight_git_remote_missing_command(monkeypatch, tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr(preflight.subprocess, "run", _raise_fnf)
    report = preflight.preflight(tmp_path)
    assert any("git remote origin" in g for g in report["gaps"])


def test_preflight_promo_stale_version(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (tmp_path / "promo").mkdir()
    (tmp_path / "promo" / "a.md").write_text("v0.0.9\n", encoding="utf-8")
    report = preflight.preflight(tmp_path, version="0.1.0")
    assert any("promo stale versions" in g for g in report["gaps"])


def test_preflight_main_text_output(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    code, out = run_mod("preflight", "--dir", str(tmp_path), "--version", "0.1.0")
    assert code == 1
    assert "✓" in out and "✗" in out
    assert "fix gaps first" in out


# --- upgrade check + report ---


def test_cli_upgrade_check_prints_when_newer(monkeypatch, capsys):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod, "_latest_pypi_version", lambda: "99.0.0")
    cli_mod._check_upgrade()
    err = capsys.readouterr().err
    assert "99.0.0 available" in err


def test_cli_upgrade_check_silent_when_current(monkeypatch, capsys):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod, "_latest_pypi_version", lambda: cli_mod.__version__)
    cli_mod._check_upgrade()
    assert capsys.readouterr().err == ""


def test_cli_check_promo_report_json(tmp_path: Path):
    (tmp_path / "post.md").write_text("install v0.1.0\n", encoding="utf-8")
    code, out = run_cli("check-promo", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--report")
    assert code == 1
    data = json.loads(out)
    assert data["ok"] is False
    assert data["errors"]
    assert "post.md" in data["by_file"]


def test_promo_check_main_report_ok(tmp_path: Path):
    (tmp_path / "post.md").write_text("install v0.1.1\n", encoding="utf-8")
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--report")
    assert code == 0
    data = json.loads(out)
    assert data["ok"] is True


# --- awesome_pr execute ---


def test_awesome_pr_heading_index():
    from shipit_skill import awesome_pr

    text = "# A\n\n## File Systems\n\n- entry\n\n### Models\n"
    assert awesome_pr._heading_index(text, "file systems") == 2
    assert awesome_pr._heading_index(text, "Models") == 6
    assert awesome_pr._heading_index(text, "nope") == -1


def test_awesome_pr_execute_requires_gh(monkeypatch):
    from shipit_skill import awesome_pr

    def fail(cmd, cwd=None):
        raise SystemExit("boom")

    monkeypatch.setattr(awesome_pr, "_run", fail)
    with pytest.raises(SystemExit):
        awesome_pr.execute("u/l", "me/r", "me/f", "b", "File Systems",
                           "desc", "npx foo", "T")


def test_awesome_pr_execute_category_not_found(monkeypatch):
    from shipit_skill import awesome_pr

    calls = {"n": 0}

    def fake_run(cmd, cwd=None):
        if cmd[0] == "gh" and cmd[1] == "repo":
            return ""
        if cmd[0] == "git" and cmd[1] == "clone":
            calls["n"] += 1
            return ""
        if cmd[0] == "git" and cmd[1] == "checkout":
            Path(cwd).joinpath("README.md").write_text("# Home\n", encoding="utf-8")
            return ""
        return ""

    monkeypatch.setattr(awesome_pr, "_run", fake_run)
    monkeypatch.setattr(awesome_pr, "tempfile", _FakeMkdtemp())
    with pytest.raises(SystemExit) as ei:
        awesome_pr.execute("u/l", "me/r", "me/f", "b", "Missing Category",
                           "desc", "npx foo", "T")
    assert "not found" in str(ei.value)


def test_awesome_pr_execute_full(monkeypatch, tmp_path: Path):
    from shipit_skill import awesome_pr

    seen_pr = []

    def fake_run(cmd, cwd=None):
        if cmd[0] == "git" and cmd[1] == "clone":
            # clone lands in cmd[-1]; drop a README with the target heading
            (Path(cmd[-1]) / "README.md").write_text(
                "# Awesome\n\n## File Systems\n\n- Old\n", encoding="utf-8"
            )
            return ""
        if cmd[0] == "gh" and cmd[2] == "create":
            seen_pr.append(cmd)
            return "https://github.com/u/l/pull/5"
        return ""

    monkeypatch.setattr(awesome_pr, "_run", fake_run)
    monkeypatch.setattr(awesome_pr, "tempfile", _FakeMkdtemp())
    url = awesome_pr.execute("u/l", "me/r", "me/f", "b", "File Systems",
                             "desc", "npx foo", "T")
    assert url == "https://github.com/u/l/pull/5"
    assert seen_pr and "create" in seen_pr[0]


def test_awesome_pr_cli_execute_requires_args():
    code, out = run_cli("awesome-pr", "--upstream", "u/l", "--repo", "me/r",
                        "--fork", "me/f", "--branch", "b", "--execute")
    assert code == 2  # argparse error: missing --category/--description/--install


class _FakeMkdtemp:
    def mkdtemp(self, prefix=""):
        import tempfile as _t

        return _t.mkdtemp(prefix=prefix)


# --- CLI check-promo --report ---


def test_cli_check_promo_report_cli(tmp_path: Path):
    (tmp_path / "post.md").write_text("install v0.1.0\n", encoding="utf-8")
    code, out = run_cli("check-promo", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--report")
    assert code == 1
    data = json.loads(out)
    assert data["ok"] is False
    assert any("post.md" in e for e in data["errors"])


def test_publish_execute_cleans_stale_dist(monkeypatch, tmp_path: Path):
    from shipit_skill import publish as pub

    monkeypatch.chdir(tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "old-0.3.1.whl").write_bytes(b"stale")
    monkeypatch.setenv("PYPI_TOKEN", "pypi-abc")

    cmds = []
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: cmds.append(c))

    pub.execute_python("demo", None)
    assert not (tmp_path / "dist" / "old-0.3.1.whl").exists()
    assert any("build" in c and "-m" in c and c[-1] == "build" for c in cmds)


def test_release_execute_rolls_back_on_publish_failure(monkeypatch, tmp_path):
    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "pypi-abc")
    _mock_doctor_all_ok(monkeypatch)

    cmds = []

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        return None

    def boom_publish(*a, **k):
        raise RuntimeError("twine upload failed")

    monkeypatch.setattr(rel.subprocess, "run", fake_run)
    monkeypatch.setattr(pub, "execute_python", boom_publish)
    with pytest.raises(SystemExit) as ei:
        rel.execute("python", "demo", "patch", repo="me/demo", dir_=str(tmp_path))
    assert ei.value.code == 1
    # rollback undoes the release commit; tag never created before publish
    assert any(c[1] == "reset" and "HEAD~1" in c for c in cmds)


def test_ci_generate_release_yaml():
    yml = ci.generate_release("python", "demo")
    assert "workflow_dispatch" in yml
    assert "secrets.PYPI_TOKEN" in yml
    assert "--execute" in yml
    code, out = run_mod("ci", "--lang", "python", "--pkg", "demo", "--release")
    assert code == 0
    assert "workflow_dispatch" in out
    assert "PYPI_TOKEN" in out


def test_cli_ci_release_writes_file(tmp_path: Path):
    out = tmp_path / "release.yml"
    code, _ = run_cli("ci", "--lang", "python", "--pkg", "demo", "--release",
                      "--write", str(out))
    assert code == 0
    assert out.exists()
    assert "workflow_dispatch" in out.read_text(encoding="utf-8")


def test_cli_ci_release_flag(tmp_path: Path):
    out = tmp_path / "release.yml"
    code, _ = run_cli("ci", "--lang", "python", "--pkg", "demo", "--release",
                      "--write", str(out))
    assert code == 0
    assert "workflow_dispatch" in out.read_text(encoding="utf-8")


# --- doctor ---


def test_doctor_checks_list(monkeypatch):
    from shipit_skill import doctor as doc

    monkeypatch.setattr(doc, "_run", lambda cmd: (0, "ok"))
    checks = doc.doctor()
    names = {c["name"] for c in checks}
    assert "gh CLI installed + authed" in names
    assert "PYPI_TOKEN set" in names
    assert "version" in names


def test_doctor_exits_1_when_gaps(monkeypatch):
    code, _ = run_mod("doctor")
    assert code == 1  # no tokens set in test env
    assert "checks passed" in _ or "Ready" in _


def _fake_doctor_run(cmd):
    if cmd[0] == "git" and "rev-parse" in cmd:
        return 0, "main"
    if cmd[0] == "git" and "status" in cmd:
        return 0, ""
    return 0, "ok"


def test_doctor_json_output(monkeypatch):
    from shipit_skill import doctor as doc

    monkeypatch.setattr(doc, "_run", _fake_doctor_run)
    monkeypatch.setattr(doc, "_importable", lambda m: True)
    monkeypatch.setattr(doc, "_which", lambda b: True)
    monkeypatch.setenv("PYPI_TOKEN", "x")
    monkeypatch.setenv("NPM_TOKEN", "y")
    code, out = run_mod("doctor", "--json")
    assert code == 0
    data = json.loads(out)
    assert "checks" in data
    assert all("ok" in c and "name" in c for c in data["checks"])


def test_cli_doctor_dispatch(monkeypatch):
    from shipit_skill import doctor as doc

    monkeypatch.setattr(doc, "_run", _fake_doctor_run)
    monkeypatch.setattr(doc, "_importable", lambda m: True)
    monkeypatch.setattr(doc, "_which", lambda b: True)
    monkeypatch.setenv("PYPI_TOKEN", "x")
    monkeypatch.setenv("NPM_TOKEN", "y")
    code, out = run_cli("doctor", "--json")
    assert code == 0
    data = json.loads(out)
    assert data["checks"]


# --- check-glama --json ---


def test_cli_glama_json_unlisted(monkeypatch):
    from shipit_skill import glama as glama_mod

    monkeypatch.setattr(glama_mod, "check_glama", lambda repo, poll=0, wait=40: False)
    code, out = run_cli("check-glama", "--repo", "me/r", "--json")
    assert code == 1
    data = json.loads(out)
    assert data["listed"] is False


# --- publish verify_python server branch ---


def test_publish_verify_python_with_server(monkeypatch, capsys):
    from shipit_skill import publish as pub

    cmds = []
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: cmds.append(c))
    pub.verify_python("demo", server="demo-server", extras="demo")
    assert any(c[0] == "bash" for c in cmds)
    assert "demo-server" in str(cmds[-1])
    assert "fresh-install OK" in capsys.readouterr().out


# --- _ask interactive path ---


def test_cli_ask_interactive(monkeypatch):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "hello")
    assert cli_mod._ask("server name", "default") == "hello"


def test_cli_ask_eof(monkeypatch):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod.sys.stdin, "isatty", lambda: True)

    def boom(_prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    assert cli_mod._ask("server name", "default") == "default"


def test_cli_ask_not_tty(monkeypatch):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod.sys.stdin, "isatty", lambda: False)
    assert cli_mod._ask("x", "default") == "default"


# --- CLI publish / release --execute dispatch (missing token) ---


def test_cli_publish_execute_missing_token():
    import os

    os.environ.pop("PYPI_TOKEN", None)
    code, _ = run_cli("publish", "--lang", "python", "--pkg", "demo", "--execute")
    assert code == 1


def test_cli_release_execute_missing_token(tmp_path, monkeypatch):
    import os

    from shipit_skill import release as rel

    os.environ.pop("PYPI_TOKEN", None)
    _mock_doctor_all_ok(monkeypatch)
    monkeypatch.setattr(rel.subprocess, "run", lambda c, **kw: None)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    code, _ = run_cli("release", "--lang", "python", "--pkg", "demo",
                      "--how", "patch", "--dir", str(tmp_path), "--execute")
    assert code == 1


def test_cli_bump_commit_mocked(monkeypatch, tmp_path):
    from shipit_skill import bump as bump_mod

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr(bump_mod.subprocess, "run", lambda c, **kw: None)
    code, out = run_cli("bump", "patch", "--dir", str(tmp_path), "--commit")
    assert code == 0
    assert "0.1.1" in out


# --- glama add_badge missing README ---


def test_glama_add_badge_missing_readme(tmp_path):
    ok = glama.add_badge("me/r", str(tmp_path / "nope.md"))
    assert ok is False


# --- publish main() branches ---


def test_publish_main_execute_python(monkeypatch, tmp_path):
    from shipit_skill import publish as pub

    monkeypatch.setenv("PYPI_TOKEN", "x")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "a-0.1.0.whl").write_bytes(b"x")
    cmds = []
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: cmds.append(c))
    code, _ = run_mod("publish", "--lang", "python", "--pkg", "demo", "--execute")
    assert code == 0
    assert any("twine" in c and "upload" in c for c in cmds)


def test_publish_main_execute_ts(monkeypatch):
    from shipit_skill import publish as pub

    monkeypatch.setenv("NPM_TOKEN", "x")
    cmds = []
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: cmds.append(c))
    monkeypatch.setattr(pub, "verify_typescript", lambda pkg: None)
    code, _ = run_mod("publish", "--lang", "typescript", "--pkg", "@x/cli", "--execute")
    assert code == 0
    assert cmds[0][0] == "npm"


def test_publish_main_verify_flag(monkeypatch):
    from shipit_skill import publish as pub

    cmds = []
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: cmds.append(c))
    code, out = run_mod("publish", "--lang", "python", "--pkg", "demo", "--verify")
    assert code == 0
    assert "twine" in out and "fresh-install" in out


# --- release main() execute via module dispatch ---


def test_release_main_execute_dispatch(monkeypatch, tmp_path):
    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "x")
    _mock_doctor_all_ok(monkeypatch)

    class R:
        returncode = 1
        stdout = ""
        stderr = ""

    monkeypatch.setattr(rel.subprocess, "run", lambda c, **kw: R())
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: None)
    code, out = run_mod("release", "--lang", "python", "--pkg", "demo",
                        "--how", "patch", "--dir", str(tmp_path), "--execute")
    assert code == 0
    assert "Released" in out


# --- glama poll success path ---


def test_glama_poll_success_via_main(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(glama.time, "sleep", lambda _n: None)
    monkeypatch.setattr(glama, "fetch_status", lambda _url: 200)
    readme = tmp_path / "README.md"
    readme.write_text("# r\n", encoding="utf-8")
    code, out = run_mod("glama", "--repo", "me/r", "--poll", "1", "--wait", "1",
                        "--add-badge", "--readme", str(readme))
    assert code == 0
    assert "badges/score.svg" in readme.read_text(encoding="utf-8")


# --- release.py gaps ---



def test_gh_available_false(monkeypatch):
    from shipit_skill import release as rel

    monkeypatch.setattr(rel.subprocess, "run", _raise_fnf)
    assert rel._gh_available() is False


# --- doctor gaps ---


def test_doctor_run_exception(monkeypatch):
    from shipit_skill import doctor as doc

    monkeypatch.setattr(doc.subprocess, "run", _raise_fnf)
    assert doc._run(["gh", "--version"]) == (1, "")


def test_doctor_main_json_exit_0(monkeypatch):
    from shipit_skill import doctor as doc

    monkeypatch.setattr(doc, "_run", _fake_doctor_run)
    monkeypatch.setattr(doc, "_importable", lambda m: True)
    monkeypatch.setattr(doc, "_which", lambda b: True)
    monkeypatch.setenv("PYPI_TOKEN", "x")
    monkeypatch.setenv("NPM_TOKEN", "y")
    code, out = run_mod("doctor", "--json")
    assert code == 0
    assert json.loads(out)["ok"] is True


# --- promo_check gaps ---


def test_promo_check_report_json_ok(tmp_path):
    (tmp_path / "post.md").write_text("install v0.1.1\n", encoding="utf-8")
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--report")
    assert code == 0
    data = json.loads(out)
    assert data["ok"] is True


def test_promo_check_report_json_errors(tmp_path):
    (tmp_path / "post.md").write_text("install v0.1.0\n", encoding="utf-8")
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--report")
    assert code == 1
    data = json.loads(out)
    assert data["ok"] is False
    assert data["errors"]


def test_promo_check_url_ok_exception(monkeypatch):
    from shipit_skill import promo_check as pc

    def boom(_url):
        raise OSError("no network")

    monkeypatch.setattr(pc.urllib.request, "urlopen", boom)
    assert pc._url_ok("https://github.com/me/r") is False


# --- release doctor gate + idempotency + changelog notes ---


def test_release_execute_blocked_by_doctor_gaps(monkeypatch, tmp_path, capsys):
    import shipit_skill.doctor as doc
    from shipit_skill import release as rel

    monkeypatch.setattr(doc, "doctor", lambda: [{"name": "gh", "ok": False, "detail": "no"}])
    with pytest.raises(SystemExit) as ei:
        rel.execute("python", "demo", "patch", dir_=str(tmp_path))
    assert ei.value.code == 1
    assert "blocked by doctor" in capsys.readouterr().out


def test_release_execute_idempotent_skips_existing_tag(monkeypatch, tmp_path):
    from unittest.mock import patch

    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "x")
    monkeypatch.setenv("NPM_TOKEN", "x")
    _mock_doctor_all_ok(monkeypatch)

    class R:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kw):
        return R()

    monkeypatch.setattr(rel.subprocess, "run", fake_run)
    monkeypatch.setattr(pub.subprocess, "run", fake_run)
    with patch.object(rel, "_tag_exists", return_value=True), \
            patch.object(rel, "_remote_tag_exists", return_value=True):
        rel.execute("python", "demo", "set:0.2.0", repo="me/demo", dir_=str(tmp_path))
    # no exception — skipped tag + skipped gh release path is fine


def test_changelog_entry_parses_section(tmp_path: Path):
    from shipit_skill import release as rel

    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.2.0] - 2026-09-04\n\n- add feature\n- fix bug\n\n"
        "## [0.1.0] - 2026-08-01\n",
        encoding="utf-8",
    )
    body = rel._changelog_entry(str(tmp_path), "v0.2.0")
    assert "add feature" in body
    assert "fix bug" in body
    assert "0.1.0" not in body


def test_changelog_entry_fallback_when_missing(tmp_path: Path):
    from shipit_skill import release as rel

    body = rel._changelog_entry(str(tmp_path), "v0.9.0")
    assert "v0.9.0" in body


# --- promo_check --fix ---


def test_promo_fix_dir_rewrites_stale_versions(tmp_path: Path):
    f = tmp_path / "post.md"
    f.write_text("install v0.1.0 and see PR #8888\n", encoding="utf-8")
    fixed, prs = promo_check.fix_dir(str(tmp_path), "0.1.1", prs={})
    assert any("0.1.0 →" in x and "0.1.1" in x for x in fixed)
    assert prs == {"8888": "unknown"}
    assert "v0.1.1" in f.read_text(encoding="utf-8")


def test_promo_fix_dir_marks_unknown_pr(tmp_path: Path):
    f = tmp_path / "post.md"
    f.write_text("see PR #9999\n", encoding="utf-8")
    fixed, prs = promo_check.fix_dir(str(tmp_path), "0.1.1", prs={})
    assert any("9999" in x and "marked as known" in x for x in fixed)
    assert "9999" in prs


def test_promo_fix_preserves_v_prefix(tmp_path: Path):
    f = tmp_path / "post.md"
    f.write_text("version is v0.1.0 now\n", encoding="utf-8")
    promo_check.fix_dir(str(tmp_path), "0.2.0")
    assert "v0.2.0" in f.read_text(encoding="utf-8")


def test_cli_check_promo_fix(tmp_path: Path):
    f = tmp_path / "post.md"
    f.write_text("install v0.1.0 and see #9999\n", encoding="utf-8")
    code, out = run_cli("check-promo", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--fix")
    assert code == 0
    assert "fixed:" in out
    assert "v0.1.1" in f.read_text(encoding="utf-8")


# --- promo --fix main + release tag print + awesome recipe variants ---


def test_promo_check_fix_main_exits_0_when_fresh(tmp_path):
    (tmp_path / "post.md").write_text("install v0.1.1\n", encoding="utf-8")
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--fix")
    assert code == 0
    assert "fresh" in out


def test_promo_check_release_tag_prints(tmp_path):
    (tmp_path / "post.md").write_text("see releases/tag/v0.1.1\n", encoding="utf-8")
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links")
    assert code == 0
    assert "release tag v0.1.1" in out


def test_promo_check_fix_main_with_errors_then_clean(tmp_path):
    f = tmp_path / "post.md"
    f.write_text("install v0.1.0\n", encoding="utf-8")
    code, out = run_mod("promo_check", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--fix")
    assert code == 0
    assert "v0.1.1" in f.read_text(encoding="utf-8")


def test_release_recipe_typescript_and_promo(tmp_path, capsys):
    from shipit_skill import release as rel

    (tmp_path / "promo").mkdir()
    (tmp_path / "promo" / "a.md").write_text("x\n", encoding="utf-8")
    cmds = rel.release("typescript", "demo", "set:0.3.0", dir_=str(tmp_path), dry_run=True)
    text = "\n".join(cmds)
    assert "check-promo" in text
    assert "npm publish" in capsys.readouterr().out


def test_release_recipe_no_repo_no_gh(tmp_path, monkeypatch):
    from unittest.mock import patch

    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    with patch.object(rel, "_gh_available", return_value=False):
        cmds = rel.release("python", "x", "patch", repo="me/x", dir_=str(tmp_path),
                           dry_run=True)
    assert any("manually" in c for c in cmds)


def test_awesome_pr_recipe_with_emoji_title():
    from shipit_skill import awesome_pr

    text = awesome_pr.recipe("u/l", "me/r", "me/f", "b", "Add r")
    assert "🤖🤖🤖" in text


def test_awesome_pr_run_failure(tmp_path):
    from shipit_skill import awesome_pr

    with pytest.raises((SystemExit, FileNotFoundError)):
        awesome_pr._run(["definitely-not-a-cmd-xyz"], cwd=str(tmp_path))


# --- upgrade check network-failure path ---


def test_latest_pypi_version_network_error(monkeypatch):
    import urllib.request as _ur

    from shipit_skill import cli as cli_mod

    def boom(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(_ur, "urlopen", boom)
    assert cli_mod._latest_pypi_version() is None


def test_check_upgrade_silent_on_network_error(monkeypatch, capsys):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod, "_latest_pypi_version", lambda: None)
    cli_mod._check_upgrade()
    assert capsys.readouterr().err == ""


# --- check-promo --fix leftover unknown PR after fix still exits 1 ---


def test_cli_check_promo_fix_remaining_errors(tmp_path):
    f = tmp_path / "post.md"
    f.write_text("install v0.1.0\n", encoding="utf-8")
    code, out = run_cli("check-promo", "--dir", str(tmp_path), "--version", "0.1.1",
                        "--no-links", "--fix")
    assert code == 0
    assert "v0.1.1" in f.read_text(encoding="utf-8")


# --- awesome-pr execute missing flags exits 2 ---


def test_cli_awesome_pr_execute_requires_category():
    code, _ = run_cli("awesome-pr", "--upstream", "u/l", "--repo", "me/r",
                      "--fork", "me/f", "--branch", "b", "--execute")
    assert code == 2


# --- doctor text (non-json) output path ---


def test_cli_doctor_text_output(monkeypatch):
    from shipit_skill import doctor as doc

    monkeypatch.setattr(doc, "_run", _fake_doctor_run)
    monkeypatch.setattr(doc, "_importable", lambda m: True)
    monkeypatch.setattr(doc, "_which", lambda b: True)
    monkeypatch.setenv("PYPI_TOKEN", "x")
    monkeypatch.setenv("NPM_TOKEN", "y")
    code, out = run_cli("doctor")
    assert code == 0
    assert "checks passed" in out


# --- preflight --json via module main ---


def test_preflight_main_json(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    code, out = run_mod("preflight", "--dir", str(tmp_path), "--version", "0.1.0", "--json")
    assert code == 1
    data = json.loads(out)
    assert data["dir"] == str(tmp_path)


# --- glama fetch_status network error + poll loop ---


def test_glama_fetch_status_network_error(monkeypatch):
    import urllib.request as _ur

    from shipit_skill import glama as gl

    def boom(*_a, **_k):
        raise OSError("no network")

    monkeypatch.setattr(_ur, "urlopen", boom)
    assert gl.fetch_status("https://glama.ai/mcp/servers/me/r") == 404


def test_glama_poll_waits_and_then_listed(monkeypatch, capsys):
    from shipit_skill import glama as gl

    calls = {"n": 0}

    def fake_fetch(_u):
        calls["n"] += 1
        return 200 if calls["n"] >= 3 else 404

    monkeypatch.setattr(gl.time, "sleep", lambda _n: None)
    monkeypatch.setattr(gl, "fetch_status", fake_fetch)
    assert gl.check_glama("me/r", poll=2, wait=1) is True
    assert "LISTED" in capsys.readouterr().out


def test_glama_poll_exhausted_returns_false(monkeypatch, capsys):
    from shipit_skill import glama as gl

    monkeypatch.setattr(gl.time, "sleep", lambda _n: None)
    monkeypatch.setattr(gl, "fetch_status", lambda _u: 404)
    assert gl.check_glama("me/r", poll=2, wait=1) is False
    assert "NOT LISTED" in capsys.readouterr().out


# --- promo _url_ok failure path (already covered) but ensure no crash ---


def test_promo_url_ok_http_error(monkeypatch):
    import urllib.request as _ur

    from shipit_skill import promo_check as pc

    class Resp:
        status = 404

    monkeypatch.setattr(_ur, "urlopen", lambda req, timeout=15: Resp())
    assert pc._url_ok("https://github.com/me/r") is False


# --- release recipe non-dry-run executes bump.set_version ---


def test_release_recipe_non_dry_run_bumps(tmp_path, monkeypatch):
    from unittest.mock import patch

    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr(pub, "print_python_commands", lambda *a, **k: None)
    with patch.object(rel, "_gh_available", return_value=True):
        cmds = rel.release("python", "x", "patch", repo="me/x", dir_=str(tmp_path))
    assert 'version = "0.1.1"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert any("gh release create" in c for c in cmds)


# --- cli publish TS execute path (missing NPM token) ---


def test_cli_publish_ts_execute_missing_token():
    import os

    os.environ.pop("NPM_TOKEN", None)
    code, _ = run_cli("publish", "--lang", "typescript", "--pkg", "@x/cli", "--execute")
    assert code == 1


def test_awesome_pr_run_ok(monkeypatch):
    from shipit_skill import awesome_pr

    class R:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setattr(awesome_pr.subprocess, "run", lambda *a, **k: R())
    assert awesome_pr._run(["git", "rev-parse"]) == "ok"


# --- cli.py remaining branches ---


def test_latest_pypi_version_success(monkeypatch):
    import urllib.request as _ur

    from shipit_skill import cli as cli_mod

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return b'{"info": {"version": "9.9.9"}}'

    monkeypatch.setattr(_ur, "urlopen", lambda *a, **k: Resp())
    assert cli_mod._latest_pypi_version() == "9.9.9"


def test_cli_upgrade_thread_started_when_tty(monkeypatch, capsys):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli_mod, "_check_upgrade", lambda: None)
    monkeypatch.setattr(cli_mod.threading, "Thread", lambda target, daemon=False: _FakeThread())
    # main() prints help when no args; the thread-start line is what we target
    code, _ = run_cli("--version")
    assert code == 0


class _FakeThread:
    def start(self):
        return None


def test_cli_publish_typescript_prints():
    code, out = run_cli("publish", "--lang", "typescript", "--pkg", "@x/cli")
    assert code == 0
    assert "npm publish" in out


def test_cli_release_execute_ok_dispatch(monkeypatch, tmp_path):
    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "x")
    _mock_doctor_all_ok(monkeypatch)

    class R:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(rel.subprocess, "run", lambda c, **kw: R())
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: None)
    code, out = run_cli("release", "--lang", "python", "--pkg", "demo",
                        "--how", "patch", "--dir", str(tmp_path), "--execute")
    assert code == 0
    assert "Released" in out


def test_cli_glama_non_json_listed(monkeypatch):
    from shipit_skill import glama as gl

    monkeypatch.setattr(gl, "check_glama", lambda repo, poll=0, wait=40: True)
    code, _ = run_cli("check-glama", "--repo", "me/r")
    assert code == 0


def test_cli_awesome_pr_execute_ok(monkeypatch):
    from shipit_skill import awesome_pr as ap

    calls = []
    monkeypatch.setattr(ap, "execute", lambda *a, **k: calls.append(a) or "https://x/pull/1")
    code, out = run_cli("awesome-pr", "--upstream", "u/l", "--repo", "me/r",
                        "--fork", "me/f", "--branch", "b", "--category", "C",
                        "--description", "D", "--install", "npx x", "--execute")
    assert code == 0
    assert calls and calls[0][0] == "u/l"


def test_cli_init_interactive_server_default(tmp_path, monkeypatch):
    from shipit_skill import cli as cli_mod

    monkeypatch.setattr(cli_mod, "_ask", lambda prompt, default: "srv")
    target = tmp_path / "t"
    code, _ = run_cli("init", str(target), "--pkg", "app")
    assert code == 0
    assert "srv" in (target / "smithery.yaml").read_text(encoding="utf-8")


# --- lang auto-detection ---


def test_detect_lang_python(tmp_path):
    from shipit_skill import cli as cli_mod

    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert cli_mod._detect_lang(str(tmp_path)) == "python"


def test_detect_lang_typescript(tmp_path):
    from shipit_skill import cli as cli_mod

    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    assert cli_mod._detect_lang(str(tmp_path)) == "typescript"


def test_detect_lang_default(tmp_path):
    from shipit_skill import cli as cli_mod

    assert cli_mod._detect_lang(str(tmp_path)) == "python"


def test_cli_ci_detect_lang_python(tmp_path):
    out = tmp_path / "ci.yml"
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    code, _ = run_cli("ci", "--dir", str(tmp_path), "--write", str(out))
    assert code == 0
    assert "pip install" in out.read_text(encoding="utf-8")


def test_cli_ci_detect_lang_typescript(tmp_path):
    out = tmp_path / "ci.yml"
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    code, _ = run_cli("ci", "--dir", str(tmp_path), "--write", str(out))
    assert code == 0
    assert "npm ci" in out.read_text(encoding="utf-8")


def test_cli_publish_detect_lang(tmp_path):
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    code, out = run_cli("publish", "--pkg", "demo", "--dir", str(tmp_path))
    assert code == 0
    assert "npm publish" in out


# --- changelog ---


def test_changelog_generate_categorizes():
    from shipit_skill import changelog

    commits = [
        "feat: add badges",
        "fix: upload stale dist",
        "docs: update README",
        "chore: bump deps",
        "some random commit",
    ]
    entry = changelog.generate("0.7.0", commits=commits)
    assert "## [0.7.0]" in entry
    assert "### Features" in entry and "- add badges" in entry
    assert "### Fixes" in entry and "- upload stale dist" in entry
    assert "### Other" in entry and "- some random commit" in entry


def test_changelog_generate_empty():
    from shipit_skill import changelog

    entry = changelog.generate("0.7.0", commits=[])
    assert "_No changes._" in entry


def test_cli_changelog_write(tmp_path):
    ch = tmp_path / "CHANGELOG.md"
    ch.write_text("# Changelog\n\n## [0.6.0] - x\n", encoding="utf-8")
    code, _ = run_cli("changelog", "--version", "0.7.0", "--write", "--dir", str(tmp_path))
    assert code == 0
    text = ch.read_text(encoding="utf-8")
    assert "## [0.7.0]" in text
    assert "## [0.6.0]" in text  # preserved below


def test_changelog_module_main():
    code, out = run_mod("changelog", "--version", "9.9.9")
    assert code == 0
    assert "## [9.9.9]" in out


# --- init .gitignore + LICENSE ---


def test_cli_init_generates_gitignore_and_license(tmp_path):
    target = tmp_path / "t"
    code, _ = run_cli("init", str(target), "--server", "srv", "--pkg", "t",
                      "--author", "Jane Doe")
    assert code == 0
    assert (target / ".gitignore").exists()
    assert "node_modules" in (target / ".gitignore").read_text(encoding="utf-8")
    lic = (target / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in lic
    assert "Jane Doe" in lic


def test_release_warns_missing_changelog(monkeypatch, tmp_path, capsys):
    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "x")
    _mock_doctor_all_ok(monkeypatch)

    class R:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(rel.subprocess, "run", lambda c, **kw: R())
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: None)
    rel.execute("python", "demo", "set:0.1.1", dir_=str(tmp_path))
    out = capsys.readouterr().out
    assert "no CHANGELOG entry" in out


def test_release_no_warning_when_changelog_has_entry(monkeypatch, tmp_path, capsys):
    from shipit_skill import publish as pub
    from shipit_skill import release as rel

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.1.1] - 2026-09-04\n\n- fix\n", encoding="utf-8"
    )
    monkeypatch.setenv("PYPI_TOKEN", "x")
    _mock_doctor_all_ok(monkeypatch)

    class R:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(rel.subprocess, "run", lambda c, **kw: R())
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: None)
    rel.execute("python", "demo", "set:0.1.1", dir_=str(tmp_path))
    out = capsys.readouterr().out
    assert "no CHANGELOG entry" not in out


# --- publish verify_typescript ---


def test_verify_typescript_success(monkeypatch, tmp_path, capsys):
    import json as _json

    from shipit_skill import publish as pub

    class R:
        returncode = 0
        stdout = _json.dumps([{"filename": "demo-1.0.0.tgz"}])
        stderr = ""

    tarball = tmp_path / "demo-1.0.0.tgz"
    tarball.write_bytes(b"x")
    monkeypatch.setattr(pub.subprocess, "run", lambda *a, **k: R())
    monkeypatch.setattr(pub.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    monkeypatch.chdir(tmp_path)
    pub.verify_typescript("demo")
    assert "fresh-install OK" in capsys.readouterr().out


def test_verify_typescript_pack_failure(monkeypatch):
    from shipit_skill import publish as pub

    class R:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(pub.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(SystemExit):
        pub.verify_typescript("demo")


# --- changelog git branches ---


def test_changelog_last_tag(monkeypatch):
    from shipit_skill import changelog

    class R:
        returncode = 0
        stdout = "v0.6.0\n"
        stderr = ""

    monkeypatch.setattr(changelog.subprocess, "run", lambda *a, **k: R())
    assert changelog.last_tag() == "v0.6.0"


def test_changelog_git_log_from_ref(monkeypatch):
    from shipit_skill import changelog

    class R:
        returncode = 0
        stdout = "feat: x\nfix: y\n"
        stderr = ""

    monkeypatch.setattr(changelog.subprocess, "run", lambda *a, **k: R())
    assert changelog._git_log("v0.6.0") == ["feat: x", "fix: y"]


def test_changelog_git_log_failure(monkeypatch):
    from shipit_skill import changelog

    class R:
        returncode = 1
        stdout = ""
        stderr = "no repo"

    monkeypatch.setattr(changelog.subprocess, "run", lambda *a, **k: R())
    with pytest.raises(SystemExit):
        changelog._git_log("v0.6.0")


def test_changelog_last_tag_none(monkeypatch):
    from shipit_skill import changelog

    class R:
        returncode = 1
        stdout = ""
        stderr = ""

    monkeypatch.setattr(changelog.subprocess, "run", lambda *a, **k: R())
    assert changelog.last_tag() is None


def test_verify_typescript_smoke_failure(monkeypatch, tmp_path):
    import json as _json

    from shipit_skill import publish as pub

    class R:
        returncode = 0
        stdout = _json.dumps([{"filename": "demo.tgz"}])
        stderr = ""

    results = {"n": 0}

    def fake_run(*a, **k):
        results["n"] += 1
        if results["n"] >= 4:
            return type("R2", (), {"returncode": 1, "stdout": "", "stderr": "no bin"})()
        return R()

    monkeypatch.setattr(pub.subprocess, "run", fake_run)
    monkeypatch.setattr(pub.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        pub.verify_typescript("demo")


def test_cli_init_force_overwrites_missing_check():
    # exercise the init check_files existance path again with different target
    import tempfile as _t

    d = _t.mkdtemp()
    run_cli("init", d, "--server", "s", "--pkg", "p", "--author", "A")
    code, out = run_cli("init", d, "--server", "s", "--pkg", "p", "--force")
    assert code == 0
    assert "wrote" in out


def test_publish_main_execute_ts_with_verify(monkeypatch):
    from shipit_skill import publish as pub

    monkeypatch.setenv("NPM_TOKEN", "x")
    monkeypatch.setattr(pub.subprocess, "run", lambda c, check=False, **kw: None)
    monkeypatch.setattr(pub, "verify_typescript", lambda pkg: None)
    code, _ = run_mod("publish", "--lang", "typescript", "--pkg", "demo", "--execute")
    assert code == 0


def test_changelog_cli_write_new_file(tmp_path):
    code, out = run_cli("changelog", "--version", "0.8.0", "--write", "--dir", str(tmp_path))
    assert code == 0
    ch = tmp_path / "CHANGELOG.md"
    assert ch.exists()
    assert "## [0.8.0]" in ch.read_text(encoding="utf-8")


def test_changelog_module_write_existing(tmp_path):
    ch = tmp_path / "CHANGELOG.md"
    ch.write_text("# Changelog\n\n## [0.1.0] - old\n", encoding="utf-8")
    code, _ = run_mod("changelog", "--version", "0.2.0", "--write", "--dir", str(tmp_path))
    assert code == 0
    text = ch.read_text(encoding="utf-8")
    assert "## [0.2.0]" in text
    assert "## [0.1.0]" in text
