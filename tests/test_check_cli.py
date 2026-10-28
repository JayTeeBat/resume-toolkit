"""CLI exit codes, warning policy and working-directory input selection."""

import json
import shutil

import pytest
from conftest import FIXTURES
from typer.testing import CliRunner

from resume_toolkit.cli import app

runner = CliRunner()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    for name in ("resume.json", "variants.toml"):
        shutil.copyfile(FIXTURES / name, tmp_path / name)
    (tmp_path / "resume-checks.toml").write_text('enabled = ["lengths", "punctuation"]')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_clean_check_reads_working_directory(workspace) -> None:
    result = runner.invoke(app, ["check", "--fast"])
    assert result.exit_code == 0, result.output
    assert "0 hard violation(s), 0 soft warning(s)" in result.output


@pytest.mark.parametrize(
    ("text", "strict", "code", "severity"),
    [
        ("Build engines.", False, 1, "hard"),
        ("Build reliable engines.", False, 0, "soft"),
        ("Build reliable engines.", True, 1, "soft"),
    ],
)
def test_exit_codes_and_json_warning_details(
    workspace, text, strict, code, severity
) -> None:
    path = workspace / "resume.json"
    data = json.loads(path.read_text())
    data["work"][0]["highlights"] = [text]
    path.write_text(json.dumps(data))
    args = ["check", "--fast", "--format", "json"] + (["--strict"] if strict else [])
    result = runner.invoke(app, args)
    assert result.exit_code == code, result.output
    (violation,) = json.loads(result.output)
    assert violation["severity"] == severity
    assert violation["text"] == text
    assert violation["where"].startswith("$.work[0].highlights[0]")
    assert violation["fix"]
    assert violation["rule"] == "lengths"
    result = runner.invoke(app, ["check", "--fast"])
    assert ("warning" if severity == "soft" else "error") in result.output


def test_explicit_input_paths(workspace) -> None:
    (workspace / "resume.json").rename(workspace / "other.json")
    (workspace / "resume-checks.toml").rename(workspace / "policy.toml")
    result = runner.invoke(
        app,
        [
            "check",
            "other.json",
            "--config",
            "policy.toml",
            "--variants",
            "variants.toml",
            "--fast",
        ],
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "args", [["--format", "xml"], ["missing.json"], ["--config", "bad.toml"]]
)
def test_input_errors_exit_two(workspace, args) -> None:
    (workspace / "bad.toml").write_text("unknown = 1")
    result = runner.invoke(app, ["check", "--fast", *args])
    assert result.exit_code == 2
    assert "error" in result.output
