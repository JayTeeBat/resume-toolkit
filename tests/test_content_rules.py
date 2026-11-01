"""Evidence and wording policy apply to the content each cut actually keeps."""

from dataclasses import replace

import pytest

from resume_toolkit.checks import run_checks
from resume_toolkit.checks.config import (
    CheckConfig,
    ConfigError,
    SkillEvidence,
    load_config,
)
from resume_toolkit.variants import Variant

CUTS = {
    "short": Variant("short", "", frozenset(), publish=True),
    "full": Variant("full", "", frozenset({"*"}), publish=True),
}


def check(resume, **kwargs):
    return run_checks(resume, CheckConfig(**kwargs), CUTS, fast=True)


@pytest.mark.parametrize("field", ["basics", "summary", "highlight"])
@pytest.mark.parametrize("keyword", ["Rust", " Rust / Go & / ", "Systems design"])
def test_evidence_boundaries_and_sentence_fields(field, keyword):
    term = "systems design" if keyword == "Systems design" else "rust"
    data = {"skills": [{"name": "Engineering", "keywords": [keyword]}]}
    text = f"Built {term} tools."
    if field == "basics":
        data["basics"] = {"summary": text}
    else:
        data["work"] = [
            {"summary": text} if field == "summary" else {"highlights": [text]}
        ]
    assert check(data, enabled=["skill_evidence"]) == []
    data["basics"] = {"summary": f"Built x{term}y."}
    data.pop("work", None)
    failures = check(data, enabled=["skill_evidence"])
    assert len(failures) == 2
    assert all(v.severity == "soft" for v in failures)
    assert failures[0].where == f'short: skill "{keyword}" (Engineering)'
    assert failures[0].text == "has no evidence in any summary or highlight"


def test_evidence_alias_exempt_stale_and_filtering():
    data = {
        "skills": [{"name": "Engineering", "keywords": ["Systems design", "Rust"]}],
        "work": [
            {
                "highlights": ["Built architectures."],
                "x-highlights": {"architectures": ["full"]},
            }
        ],
    }
    policy = SkillEvidence(
        aliases={"Systems design": ["architectures"]}, exempt=["rust"]
    )
    failures = check(data, enabled=["skill_evidence"], skill_evidence=policy)
    assert len(failures) == 1
    assert failures[0].where.startswith("short:")
    data["skills"][0]["x-tags"] = ["full"]
    assert check(data, enabled=["skill_evidence"], skill_evidence=policy) == []
    data["skills"] = []
    failures = check(data, enabled=["skill_evidence"], skill_evidence=policy)
    assert len(failures) == 2
    assert all(v.severity == "hard" for v in failures)
    assert all("unknown skill keyword" in v.fix for v in failures)
    data = {"skills": [{"keywords": ["Rust"]}], "basics": {"summary": "Rust."}}
    assert (
        check(
            data,
            enabled=["skill_evidence"],
            skill_evidence=SkillEvidence(aliases={"Rust": ["unused"]}),
        )
        == []
    )


def test_weak_phrases_levels_boundaries_and_deduplication():
    data = {
        "basics": {"summary": "Our tooling."},
        "work": [
            {
                "name": "Example",
                "position": "Engineer",
                "summary": "Helped build tools.",
                "highlights": ["Built tools.", "Worked on robust designs."],
                "x-highlights": {"Built tools": ["full"]},
            }
        ],
    }
    failures = check(data, enabled=["weak_phrases"])
    assert [v.severity for v in failures] == ["soft", "hard", "hard", "soft"]
    assert all("in short, full" in v.where for v in failures)
    assert all("owned action/outcome" in v.fix for v in failures)
    assert ".highlights[1]" in failures[2].where
    data = {"basics": {"summary": "Flowers showered over workable designs."}}
    assert check(data, enabled=["weak_phrases"]) == []


def test_weak_phrase_filtering_and_replacement(tmp_path):
    path = tmp_path / "checks.toml"
    path.write_text(
        'enabled = ["weak_phrases"]\nweak_phrases = { hard = ["vague"], soft = [] }'
    )
    config = load_config(path)
    data = {
        "work": [
            {
                "highlights": ["Helped our team.", "Vague results."],
                "x-highlights": {"Vague": ["full"]},
            }
        ]
    }
    failures = run_checks(data, config, CUTS, fast=True)
    assert len(failures) == 1
    assert "in full" in failures[0].where
    path.write_text("weak_phrases = { hard = [] }")
    assert load_config(path).weak_phrases["soft"] == CheckConfig().weak_phrases["soft"]


@pytest.mark.parametrize(
    "body",
    [
        "skill_evidence = { extra = [] }",
        "skill_evidence = { aliases = [] }",
        'skill_evidence = { aliases = { Rust = "rust" } }',
        'skill_evidence = { aliases = { Rust = [""] } }',
        "skill_evidence = { exempt = [1] }",
        'weak_phrases = { hard = ["OUR"] }',
        'weak_phrases = { hard = "helped" }',
        'weak_phrases = { soft = [""] }',
        "weak_phrases = { other = [] }",
        'severity = { lengths = "warning" }',
        "severity = { lengths = [] }",
        "role_highlights = { short = [] }",
        "role_highlights = { short = [{ min = 2, max = 1 }] }",
        "role_highlights = { short = [{ max = -1 }] }",
        "role_highlights = { short = [{ max = true }] }",
        'role_highlights = { short = [{ since = "2020-01" }] }',
        'role_highlights = { short = [{ max = 1, before = "2020-13" }] }',
        'role_highlights = { short = [{ max = 1, since = "2020-01", '
        'before = "2020-01" }] }',
        "role_highlights = { short = [{ max = 1 }, { min = 2 }] }",
    ],
)
def test_invalid_new_policy(tmp_path, body):
    path = tmp_path / "checks.toml"
    path.write_text(body)
    with pytest.raises(ConfigError):
        load_config(path)


def test_unknown_severity_lists_rules(tmp_path):
    path = tmp_path / "checks.toml"
    path.write_text('severity = { typo = "hard" }')
    with pytest.raises(ConfigError, match="valid rules:.*skill_evidence.*lengths"):
        load_config(path)


def test_bands_boundaries_limits_and_required_roles(tmp_path):
    path = tmp_path / "checks.toml"
    path.write_text(
        'enabled = ["role_highlights"]\n[role_highlights]\n'
        'short = [{since="2020-11", min=3, max=5}, '
        '{before="2020-11", max=1}]'
    )
    config = load_config(path)
    role = {
        "name": "Example",
        "position": "Engineer",
        "startDate": "2020-11",
        "highlights": ["Built tools."] * 3,
    }
    assert run_checks({"work": [role]}, config, CUTS, fast=True) == []
    role["startDate"] = "2020-10"
    (failure,) = run_checks({"work": [role]}, config, CUTS, fast=True)
    assert "Example — Engineer; in short" in failure.where
    assert "3 nonblank" in failure.text
    assert "maximum 1" in failure.text
    assert "drop 2" in failure.fix
    assert "x-highlights" in failure.fix
    role["x-tags"] = ["full"]
    assert run_checks({"work": [role]}, config, CUTS, fast=True) == []
    role["startDate"] = "2020-11"
    assert "x-tags" in run_checks({"work": [role]}, config, CUTS, fast=True)[0].where
    config = replace(
        config, role_highlights={"short": [{"since": "2020-11", "min": 0}]}
    )
    assert run_checks({"work": [role]}, config, CUTS, fast=True) == []
    path.write_text(
        'role_highlights = { short = [{ since="2020-01", min=1 }, '
        '{before="2021-01", max=2}] }'
    )
    with pytest.raises(ConfigError, match=r"bands \[0\].*and \[1\].*overlap"):
        load_config(path)


@pytest.mark.parametrize("level", ["soft", "hard"])
def test_severity_forces_mixed_rules(level):
    data = {"work": [{"highlights": ["Helped.", "Built robust tools."]}]}
    failures = check(
        data,
        enabled=["lengths", "weak_phrases"],
        severity={"lengths": level, "weak_phrases": level},
    )
    assert {v.rule for v in failures} == {"lengths", "weak_phrases"}
    assert {v.severity for v in failures} == {level}


def test_legacy_zero_minimum_since_retains_survival_requirement():
    data = {"work": [{"startDate": "2020-01", "x-tags": ["full"]}]}
    failures = check(
        data,
        enabled=["role_highlights"],
        role_highlights={"short": {"min": 0, "since": "2020-01"}},
    )
    assert len(failures) == 1
    assert "x-tags" in failures[0].where
