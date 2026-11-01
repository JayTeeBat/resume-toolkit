"""Run the public CLI from a content directory without mocked asset paths."""

import json
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
@pytest.mark.parametrize("site_formats", [None, '["html"]'])
def test_example_build_all_formats(example_workspace, site_formats):
    if site_formats:
        path = example_workspace / "variants.toml"
        path.write_text(
            path.read_text().replace(
                "publish = true", f"publish = true\nformats = {site_formats}"
            )
        )
    run_cli(example_workspace, "build")
    for variant in ("full", "short"):
        for fmt in ("html", "json", "md"):
            assert (example_workspace / "dist" / f"resume-{variant}.{fmt}").is_file()
    assert (example_workspace / "dist" / "Ada-Lovelace-Resume.pdf").is_file()
    assert (example_workspace / "dist" / "Ada-Lovelace-Resume-Full.pdf").is_file()
    run_cli(example_workspace, "check")


@pytest.mark.slow
def test_selected_primary_build_uses_site_filename(example_workspace):
    output = run_cli(example_workspace, "build", "-v", "short", "-f", "pdf")
    assert "Ada-Lovelace-Resume.pdf" in output
    assert (example_workspace / "dist" / "Ada-Lovelace-Resume.pdf").is_file()


def test_empty_pdf_name_is_a_clear_cli_error(example_workspace):
    path = example_workspace / "resume.json"
    data = json.loads(path.read_text())
    data["basics"]["name"] = "!!!"
    path.write_text(json.dumps(data))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from resume_toolkit.cli import app; app()",
            "build",
            "-f",
            "pdf",
        ],
        cwd=example_workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "basics.name must produce a nonempty ASCII PDF filename" in result.stdout


@pytest.mark.parametrize("published", [True, False])
@pytest.mark.parametrize("variant", ["short", "full"])
def test_selected_build_colophon_uses_first_published_cut(
    example_workspace, published, variant
):
    if not published:
        path = example_workspace / "variants.toml"
        path.write_text(path.read_text().replace("publish = true", "publish = false"))
    for fmt in ("html", "md"):
        run_cli(example_workspace, "build", "-v", variant, "-f", fmt)
        text = (example_workspace / "dist" / f"resume-{variant}.{fmt}").read_text()
        assert (f"{variant.title()} Version" in text) == (
            not published or variant != "short"
        )
