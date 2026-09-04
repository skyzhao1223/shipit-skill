"""pytest fixtures: make subprocess CLI calls under test collect coverage.

pytest-cov measures the parent interpreter only. Our tests invoke
`python -m shipit_skill.<cmd>` as subprocesses, so we propagate the COV_CORE_*
env vars pytest-cov uses for subprocess coverage.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _coverage_env(monkeypatch):
    """Forward coverage context to child processes (COV_CORE_*)."""
    cov_core_source = os.environ.get("COV_CORE_SOURCE")
    if cov_core_source:
        monkeypatch.setenv("COV_CORE_SOURCE", cov_core_source)
    cov_core_datafile = os.environ.get("COV_CORE_DATAFILE")
    if cov_core_datafile:
        monkeypatch.setenv("COV_CORE_DATAFILE", cov_core_datafile)
    cov_core_cfg = os.environ.get("COV_CORE_CONFIG")
    if cov_core_cfg:
        monkeypatch.setenv("COV_CORE_CONFIG", cov_core_cfg)
    # ensure child subprocesses also see UTF-8
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    yield
