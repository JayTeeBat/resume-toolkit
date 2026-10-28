"""Fictional data shared by toolkit tests; never load the repository CV."""

from pathlib import Path

import pytest

from resume_toolkit.model import load_resume
from resume_toolkit.variants import load_variants

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def resume() -> dict:
    return load_resume(FIXTURES / "resume.json")


@pytest.fixture(autouse=True)
def site_variants(monkeypatch) -> None:
    monkeypatch.setattr(
        "resume_toolkit.site.load_variants",
        lambda: load_variants(FIXTURES / "variants.toml"),
    )
