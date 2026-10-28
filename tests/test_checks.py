"""Each editorial rule accepts a fixture and reports actionable bad input."""

from dataclasses import replace

import pytest
from conftest import FIXTURES

from resume_toolkit.checks import RULE_FUNCTIONS, external, run_checks, structure
from resume_toolkit.checks.common import clip
from resume_toolkit.checks.config import CheckConfig
from resume_toolkit.variants import load_variants

CUTS = load_variants(FIXTURES / "variants.toml")
POLICY = CheckConfig(
    spelling="en-GB",
    proper_names={"Github": "GitHub"},
    required_fields={"education": ["institution"]},
)

CASES = [
    ("punctuation", "summary", "Build engines", "add a final period"),
    ("spelling", "summary", "Build optimized engines.", "UK spelling"),
    ("proper_names", "summary", "Build engines on Github.", 'write "GitHub"'),
    ("typography", "summary", "Build  engines.", "collapse the double space"),
    ("unit_spacing", "summary", "Build 800V engines.", 'write "800 V"'),
    ("tense", "summary", "Built engines.", "current role reads in the present"),
    ("verb_led", "highlights", ["Engine components."], "open with a verb"),
    (
        "quantified",
        "highlights",
        ["Build engines."],
        "add at least one concrete figure",
    ),
    ("lengths", "summary", "Build engines. Test them.", "write exactly 1 sentence"),
    ("highlights", "highlights", [], "add at least one bullet"),
    (
        "locations",
        "location",
        "London, County, United Kingdom",
        'write "London, United Kingdom"',
    ),
    ("tags", "x-tags", ["unknown"], 'remove "unknown"'),
    ("chronology", "startDate", "1840-01", "newest role first"),
    ("overlaps", "startDate", "1843-01", "correct the dates"),
    ("gaps", "startDate", "1845-01", "12-month gap"),
    ("dates", "startDate", "1844", "write YYYY-MM"),
]


@pytest.mark.parametrize(("rule", "field", "value", "fix"), CASES)
def test_rule_passes_then_reports_where_text_and_fix(
    resume, rule, field, value, fix
) -> None:
    check = RULE_FUNCTIONS[rule]
    assert check(resume, POLICY, CUTS) == []
    resume["work"][0][field] = value
    violations = check(resume, POLICY, CUTS)
    assert violations
    assert all(v.rule == rule and v.severity == "hard" for v in violations)
    assert any(fix in v.fix for v in violations)
    assert all(v.where.startswith("$.work[") and v.text for v in violations)
    assert all(
        "where:" in v.render() and "text:" in v.render() and "fix:" in v.render()
        for v in violations
    )


def test_skills_and_stale_allowlist(resume) -> None:
    assert structure.skills(resume, POLICY, CUTS) == []
    resume["skills"].append({"name": "Research", "keywords": ["analysis"]})
    failures = structure.skills(resume, POLICY, CUTS)
    assert len(failures) == 2
    assert "only one skills group" in failures[0].fix
    allowed = replace(POLICY, shared_skill_keywords=["Analysis"])
    assert structure.skills(resume, allowed, CUTS) == []
    resume["skills"].pop()
    assert (
        "remove this allowlist entry" in structure.skills(resume, allowed, CUTS)[0].fix
    )


def test_required_fields(resume) -> None:
    assert structure.required_fields(resume, POLICY, CUTS) == []
    resume["education"][0]["institution"] = " "
    (violation,) = structure.required_fields(resume, POLICY, CUTS)
    assert violation.where.startswith("$.education[0].institution")
    assert "supply a non-empty institution" in violation.fix


def test_gap_allowlist_and_stale_detection(resume) -> None:
    resume["work"][0]["startDate"] = "1845-01"
    policy = replace(POLICY, gap_allowlist={("1843-12", "1845-01"): "Study leave"})
    assert structure.gaps(resume, policy, CUTS) == []
    resume["work"][0]["startDate"] = "1844-01"
    (violation,) = structure.gaps(resume, policy, CUTS)
    assert violation.text == "Study leave"
    assert "remove the entry" in violation.fix


def test_roles_straddling_school_anchor_gaps(resume) -> None:
    resume["education"][0]["endDate"] = "1843-06"
    resume["work"][0]["startDate"] = "1845-01"
    assert "12-month gap" in structure.gaps(resume, POLICY, CUTS)[0].fix
    resume["education"][0]["endDate"] = "1843-12"
    assert structure.gaps(resume, POLICY, CUTS) == []


def test_bad_dates_do_not_crash_timeline_rules(resume) -> None:
    resume["education"][0]["endDate"] = "1841"
    policy = replace(POLICY, enabled=["gaps", "chronology", "overlaps"])
    violations = run_checks(resume, policy, CUTS)
    assert [v.rule for v in violations] == ["dates"]


def test_missing_sections_are_supported() -> None:
    policy = replace(
        POLICY,
        enabled=[
            r for r in POLICY.enabled if r not in {"codespell", "page_budget", "header"}
        ],
    )
    assert run_checks({}, policy, {}) == []


@pytest.mark.parametrize(
    ("count", "severity"),
    [
        (3, "soft"),
        (9, "soft"),
        (10, None),
        (30, None),
        (31, "soft"),
        (40, "soft"),
        (41, "hard"),
        (2, "hard"),
    ],
)
def test_highlight_limits(resume, count, severity) -> None:
    resume["work"][0]["highlights"] = [
        "Build " + "engine " * (count - 2) + "components."
    ]
    violations = RULE_FUNCTIONS["lengths"](resume, POLICY, CUTS)
    assert [v.severity for v in violations] == ([severity] if severity else [])
    if violations:
        assert f"found {count}" in violations[0].fix


@pytest.mark.parametrize(
    ("count", "severity"), [(25, None), (26, "soft"), (30, "soft"), (31, "hard")]
)
def test_summary_limits(resume, count, severity) -> None:
    resume["work"][0]["summary"] = "Build " + "engine " * (count - 2) + "components."
    violations = RULE_FUNCTIONS["lengths"](resume, POLICY, CUTS)
    assert [v.severity for v in violations] == ([severity] if severity else [])


def test_codespell_reports_file_and_replacement(tmp_path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("resources\n")
    assert external.codespell(tmp_path, POLICY) == []
    source.write_text("resou" + "ces\n")
    (violation,) = external.codespell(tmp_path, POLICY)
    assert "notes.txt:1" in violation.where
    assert "write resources" in violation.fix


def test_fast_skips_only_browser_rules(resume, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("fast mode launched a browser")

    for name in ("page_budget", "header"):
        monkeypatch.setitem(RULE_FUNCTIONS, name, forbidden)
    assert (
        run_checks(
            resume,
            replace(POLICY, enabled=["page_budget", "header", "punctuation"]),
            CUTS,
            fast=True,
        )
        == []
    )


@pytest.mark.slow
def test_page_budget_accepts_short_and_reports_long_document(resume) -> None:
    config = replace(POLICY, page_budget=1)
    assert external.page_budget(resume, config, CUTS) == []
    resume["work"][0]["highlights"] *= 100
    (violation,) = external.page_budget(resume, config, CUTS)
    assert violation.rule == "page_budget"
    assert "budget 1" in violation.text
    assert "trim or tag entries" in violation.fix


@pytest.mark.slow
def test_header_accepts_one_line_and_reports_screen_and_print_wrap(resume) -> None:
    assert external.header(resume, POLICY, CUTS) == []
    resume["basics"]["profiles"] = [
        {"network": f"Profile {i}", "url": f"https://example.com/{i}"}
        for i in range(20)
    ]
    violations = external.header(resume, POLICY, CUTS)
    assert len(violations) == 2
    assert "(screen)" in violations[0].where
    assert "(print)" in violations[1].where
    assert all("shorten or drop one contact item" in v.fix for v in violations)


def test_clip_preserves_short_text_and_both_ends() -> None:
    assert clip("Hello") == '"Hello"'
    assert clip("a" * 80 + "b" * 80) == '"' + "a" * 35 + "…" + "b" * 35 + '"'


@pytest.mark.parametrize("text", ["800V", "43kWh", "±3%", "25A/channel", "20°C"])
def test_unit_spacing_recognises_symbols(text) -> None:
    violations = RULE_FUNCTIONS["unit_spacing"](
        {"basics": {"summary": text}}, POLICY, CUTS
    )
    assert len(violations) == 1
    assert "insert whitespace" in violations[0].fix


@pytest.mark.parametrize(
    "text",
    [
        "800 V",
        "43 kWh",
        "±3 %",
        "25 A/channel",
        "20 °C",
        "ISO 26262",
        "3D prototype",
        "OBD2",
        "100+ resources",
    ],
)
def test_unit_spacing_accepts_spaces_and_non_units(text) -> None:
    assert (
        RULE_FUNCTIONS["unit_spacing"]({"basics": {"summary": text}}, POLICY, CUTS)
        == []
    )


def test_custom_location_pattern_has_matching_advice(resume) -> None:
    policy = replace(POLICY, location_pattern=r"[A-Z]+")
    violations = structure.locations(resume, policy, CUTS)
    assert "matching '[A-Z]+'" in violations[0].fix
    resume["work"] = [{"location": "LONDON"}]
    assert structure.locations(resume, policy, CUTS) == []


@pytest.mark.parametrize("fmt", ["YYYY", "YYYY-MM-DD"])
def test_alternative_date_formats_and_month_gap_allowlist(resume, fmt) -> None:
    for section in ("work", "education", "publications"):
        for entry in resume[section]:
            for field in ("startDate", "endDate", "releaseDate"):
                if field in entry:
                    entry[field] = (
                        entry[field][:4] if fmt == "YYYY" else entry[field] + "-01"
                    )
    policy = replace(POLICY, date_format=fmt)
    assert structure.dates(resume, policy, CUTS) == []
    resume["work"][0]["startDate"] = "1845" if fmt == "YYYY" else "1845-01-01"
    end_month = "1843-01" if fmt == "YYYY" else "1843-12"
    policy = replace(policy, gap_allowlist={(end_month, "1845-01"): "Study"})
    assert structure.gaps(resume, policy, CUTS) == []


def test_registry_and_config_have_the_same_rules() -> None:
    assert set(POLICY.enabled) == set(RULE_FUNCTIONS) | {"codespell"}
