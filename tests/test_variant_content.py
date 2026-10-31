"""Content coverage is checked after filtering, without a browser."""

from dataclasses import replace

import pytest

from resume_toolkit.checks import run_checks
from resume_toolkit.checks.config import CheckConfig, ConfigError, load_config
from resume_toolkit.variants import Variant

CUTS = {"one": Variant("one", "", frozenset(), publish=True)}
POLICY = CheckConfig(
    enabled=["required_sections", "role_highlights"],
    required_sections={"*": ["basics"], "one": ["languages"]},
    role_highlights={"one": {"min": 1, "since": "2010-06"}},
)


def coverage_resume() -> dict:
    return {
        "basics": {"name": "Alex Example"},
        "languages": [{"language": "English"}],
        "work": [
            {
                "name": "Example",
                "position": "Engineer",
                "startDate": "2010-06",
                "highlights": ["Built engines."],
            }
        ],
    }


def test_filtered_coverage_and_fast_mode() -> None:
    resume = coverage_resume()
    assert run_checks(resume, POLICY, CUTS, fast=True) == []
    resume["languages"][0]["x-tags"] = ["full"]
    resume["work"][0]["x-highlights"] = {"Built engines": ["full"]}
    failures = run_checks(resume, POLICY, CUTS, fast=True)
    assert [v.rule for v in failures] == ["required_sections", "role_highlights"]
    assert all(v.severity == "hard" for v in failures)
    assert "required_sections.one" in failures[0].fix
    assert 'x-highlights["Built engines"]' in failures[1].fix
    assert "Example — Engineer; in one" in failures[1].where
    resume["work"][0]["x-tags"] = ["full"]
    assert "x-tags" in run_checks(resume, POLICY, CUTS, fast=True)[1].where
    resume["work"][0]["startDate"] = "2010-05"
    assert len(run_checks(resume, POLICY, CUTS, fast=True)) == 1
    assert run_checks({}, CheckConfig(enabled=POLICY.enabled), CUTS, fast=True) == []


def test_without_since_only_surviving_roles_are_required() -> None:
    config = replace(
        POLICY, enabled=["role_highlights"], role_highlights={"one": {"min": 1}}
    )
    resume: dict = {"work": [{"startDate": "2000-01", "x-tags": ["full"]}]}
    assert run_checks(resume, config, CUTS, fast=True) == []
    del resume["work"][0]["x-tags"]
    assert run_checks(resume, config, CUTS, fast=True)


@pytest.mark.parametrize(
    "body",
    [
        "[role_highlights.one]\nmin = -1",
        "[role_highlights.one]\nmin = true",
        '[role_highlights.one]\nmin = 1\nsince = "2010-13"',
        '[role_highlights.one]\nmin = 1\nsince = "2010"',
        "[role_highlights.one]\nmin = 1\nextra = 2",
        '[required_sections]\none = "languages"',
    ],
)
def test_invalid_policy(tmp_path, body) -> None:
    path = tmp_path / "checks.toml"
    path.write_text(body)
    with pytest.raises(ConfigError):
        load_config(path)


@pytest.mark.parametrize("key", ["required_sections", "role_highlights"])
def test_unknown_variant_names_defined_variants(tmp_path, key) -> None:
    path = tmp_path / "checks.toml"
    value = '["languages"]' if key == "required_sections" else "{ min = 1 }"
    path.write_text(f"[{key}]\nmissing = {value}\n")
    with pytest.raises(ConfigError, match="it defines: one"):
        run_checks({}, load_config(path), CUTS, fast=True)


def test_shared_requirements_and_exemptions() -> None:
    resume = coverage_resume()
    resume["basics"] = {}
    failures = run_checks(resume, POLICY, CUTS, fast=True)
    assert len(failures) == 1
    assert 'required_sections."*"' in failures[0].fix
    exempt = replace(POLICY, variant_exemptions={"one": ["required_sections"]})
    assert run_checks(resume, exempt, CUTS, fast=True) == []


def test_missing_date_cannot_hide_a_required_role() -> None:
    resume = coverage_resume()
    del resume["work"][0]["startDate"]
    assert [v.rule for v in run_checks(resume, POLICY, CUTS, fast=True)] == ["dates"]
