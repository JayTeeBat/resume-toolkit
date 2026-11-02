"""`__version__` must follow the version declared in pyproject.toml."""

import tomllib
from pathlib import Path

import resume_toolkit

ROOT = Path(__file__).resolve().parents[1]


def test_dunder_version_matches_pyproject() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert resume_toolkit.__version__ == project["version"]
