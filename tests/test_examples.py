"""Run the public CLI from a content directory without mocked asset paths."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def example_workspace(tmp_path):
    for path in EXAMPLES.iterdir():
        if path.is_file():
            shutil.copyfile(path, tmp_path / path.name)
    return tmp_path


def run_cli(workspace, *args):
    result = subprocess.run(
        [sys.executable, "-c", "from resume_toolkit.cli import app; app()", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_example_validate_and_check(example_workspace):
    assert "valid JSON Resume" in run_cli(example_workspace, "validate")
    assert "0 hard violation(s)" in run_cli(example_workspace, "check", "--fast")


@pytest.mark.parametrize("fmt", ["html", "json", "md"])
def test_example_build_without_browser(example_workspace, fmt):
    run_cli(example_workspace, "build", "-f", fmt)
    for variant in ("full", "short"):
        assert (example_workspace / "dist" / f"resume-{variant}.{fmt}").is_file()


@pytest.mark.slow
def test_example_build_all_formats(example_workspace):
    run_cli(example_workspace, "build")
    for variant in ("full", "short"):
        for fmt in ("html", "pdf", "json", "md"):
            assert (example_workspace / "dist" / f"resume-{variant}.{fmt}").is_file()
    run_cli(example_workspace, "check")
