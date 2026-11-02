"""Config errors point to the invalid key; omitted values use documented defaults."""

import pytest

from resume_toolkit.checks.config import (
    CheckConfig,
    ConfigError,
    checked_variants,
    load_config,
    page_budget_for,
    published_variants,
)
from resume_toolkit.variants import Variant

CUTS = {
    "full": Variant("full", "", frozenset({"*"})),
    "short": Variant("short", "", frozenset(), publish=True),
    "one": Variant("one", "", frozenset(), publish=True),
}


def test_missing_and_empty_configs_use_defaults(tmp_path) -> None:
    path = tmp_path / "checks.toml"
    assert load_config(path) == CheckConfig()
    path.write_text("")
    assert load_config(path) == CheckConfig()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("unknown = 1", "unknown checks key"),
        ("page_budget = true", "page_budget: expected int"),
        ("page_budget = 0", "positive integer"),
        ("page_budget = {}", "table of variant = positive integer"),
        ("page_budget = { short = 0 }", "table of variant = positive integer"),
        ('page_budget = { short = "2" }', "table of variant = positive integer"),
        ('published_variant = "short"', "replaced in 0.2.0 by published_variants"),
        ("published_variants = [1]", "list of str"),
        ('[variant_exemptions]\nfull = ["lengths"]', "variant_exemptions"),
        ('[variant_exemptions]\nfull = "quantified"', "variant_exemptions"),
        ('spelling = "en-US"', "spelling: choose"),
        ('enabled = ["typo"]', "unknown rules"),
        ('enabled = ["dates", "dates"]', "duplicate"),
        ("enabled = [1]", "list of str"),
        ('date_format = "DD-MM"', "date_format: choose"),
        ("highlight_soft_range = [30, 10]", "minimum"),
        ("highlight_soft_range = [1, 50]", "inside highlight_hard_range"),
        ("summary_soft_max = 40", "summary_hard_max"),
        ('location_pattern = "["', "location_pattern"),
        ("[proper_names]\nName = 1", "proper_names"),
        ('[required_fields]\nwork = "name"', "required_fields"),
        ('[gap_allowlist]\n"1840..1842" = "Study"', "gap_allowlist"),
        ('[gap_allowlist]\n"1842-01..1841-01" = "Study"', "must precede"),
        ('[gap_allowlist]\n"1840-01..1841-01" = ""', "non-empty reason"),
        ("enabled = [", "checks.toml"),
    ],
)
def test_invalid_config_is_actionable(tmp_path, text, message) -> None:
    path = tmp_path / "checks.toml"
    path.write_text(text)
    with pytest.raises(ConfigError, match=message):
        load_config(path)


def test_nondefault_policy_and_gap_dates_load(tmp_path) -> None:
    path = tmp_path / "checks.toml"
    path.write_text(
        'spelling = "en-GB"\npage_budget = 3\n'
        '[gap_allowlist]\n"1840-01..1841-01" = "Study"'
    )
    config = load_config(path)
    assert config.spelling == "en-GB"
    assert config.page_budget == 3
    assert config.gap_allowlist == {("1840-01", "1841-01"): "Study"}


def test_page_budget_table_binds_only_the_cuts_it_names(tmp_path) -> None:
    path = tmp_path / "checks.toml"
    path.write_text("page_budget = { short = 2, one = 1 }")
    config = load_config(path)

    assert config.page_budget == {"short": 2, "one": 1}
    assert page_budget_for(config, "one") == 1
    assert page_budget_for(config, "full") is None
    assert page_budget_for(CheckConfig(), "full") == 2


def test_variant_rules_cover_every_published_cut_in_file_order() -> None:
    assert [v.name for v in published_variants(CheckConfig(), CUTS)] == [
        "short",
        "one",
    ]
    explicit = CheckConfig(published_variants=["one", "full"])
    assert [v.name for v in published_variants(explicit, CUTS)] == ["one", "full"]
    # Nothing published: the whole document stands in.
    assert [v.name for v in published_variants(CheckConfig(), {})] == ["all"]


def test_variant_exemptions_drop_one_rule_for_one_cut() -> None:
    config = CheckConfig(variant_exemptions={"one": ["quantified"]})

    assert [v.name for v in checked_variants("quantified", config, CUTS)] == ["short"]
    assert [v.name for v in checked_variants("header", config, CUTS)] == [
        "short",
        "one",
    ]


@pytest.mark.parametrize(
    ("config", "key"),
    [
        (CheckConfig(published_variants=["missing"]), "published_variants"),
        (CheckConfig(page_budget={"missing": 1}), "page_budget"),
        (CheckConfig(variant_exemptions={"missing": ["header"]}), "variant_exemptions"),
    ],
)
def test_unknown_variant_names_are_actionable(config, key) -> None:
    with pytest.raises(ConfigError, match=f"{key}: 'missing' not in variants.toml"):
        published_variants(config, CUTS)


@pytest.mark.parametrize(
    "value",
    [
        '"Configure"',
        "[1]",
        '[""]',
        '[" "]',
        '["configure"]',
        '["Configure systems"]',
        '[" Configure"]',
        '["Configure "]',
        '["Configure-Tools"]',
        '["Configure2"]',
    ],
)
def test_extra_verbs_rejects_invalid_entries(tmp_path, value):
    path = tmp_path / "checks.toml"
    path.write_text(f"extra_verbs = {value}")
    with pytest.raises(ConfigError, match="extra_verbs"):
        load_config(path)


def test_extra_verbs_accepts_empty_list(tmp_path):
    path = tmp_path / "checks.toml"
    path.write_text("extra_verbs = []")
    assert load_config(path).extra_verbs == []
