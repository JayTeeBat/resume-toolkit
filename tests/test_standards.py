"""The standards register must follow the repository's real pins."""

import re
from pathlib import Path

from resume_toolkit.checks.language import SI_BROCHURE, UNIT_SYMBOLS

ROOT = Path(__file__).resolve().parents[1]


def test_standards_pins() -> None:
    register = (ROOT / "docs/standards.md").read_text()
    source = (ROOT / "src/resume_toolkit/assets/schema/SOURCE.md").read_text()
    schema_pin = re.search(r"Pinned commit \| `([a-f0-9]{40})`", source)
    assert schema_pin
    assert schema_pin[1] in register
    assert "draft-07" in source
    assert "draft-07" in register
    kit_row = next(
        line for line in register.splitlines() if "| repo-standard-kit |" in line
    )
    pins = []
    for name in (
        ".github/workflows/compliance.yml",
        ".pre-commit-config.yaml",
        "AGENTS.md",
        "README.md",
    ):
        pins += re.findall(
            r"repo-standard-kit(?:\.git)?(?:@|/(?:tree|blob)/)(v[\d.]+)",
            (ROOT / name).read_text(),
        )
    assert pins
    assert all(pin in kit_row for pin in pins)
    assert 'profile = "python-single"' in (ROOT / "pyproject.toml").read_text()
    assert "python-single" in kit_row
    si_row = next(line for line in register.splitlines() if "SI Brochure" in line)
    assert SI_BROCHURE in si_row
    assert "Nm" not in UNIT_SYMBOLS
    assert "sitemap/0.9" in (ROOT / "src/resume_toolkit/site.py").read_text()
    assert "| 0.9 |" in register
