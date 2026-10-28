"""Config errors point to the invalid key; omitted values use documented defaults."""

import pytest

from resume_toolkit.checks.config import (
    CheckConfig,
    ConfigError,
    load_config,
    published_variant,
)


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


def test_unknown_published_variant_is_actionable() -> None:
    with pytest.raises(ConfigError, match="published_variant"):
        published_variant(CheckConfig(published_variant="missing"), {})
