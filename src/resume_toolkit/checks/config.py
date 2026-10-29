"""Strict configuration loading; defaults are documented in docs/checks.md."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from ..variants import Variant

RULES = (
    "punctuation",
    "spelling",
    "proper_names",
    "typography",
    "unit_spacing",
    "tense",
    "verb_led",
    "quantified",
    "lengths",
    "highlights",
    "locations",
    "tags",
    "chronology",
    "overlaps",
    "gaps",
    "skills",
    "required_fields",
    "dates",
    "codespell",
    "page_budget",
    "header",
    "page_breaks",
)

#: Rules that print or lay out the CV in Chromium; `--fast` skips them.
BROWSER_RULES = frozenset({"page_budget", "header", "page_breaks"})
#: Rules that check each published cut rather than the whole document.
VARIANT_RULES = BROWSER_RULES | {"quantified"}


class ConfigError(ValueError):
    """Invalid resume-checks.toml or incompatible variant selection."""


@dataclass(frozen=True)
class CheckConfig:
    enabled: list[str] = field(default_factory=lambda: list(RULES))
    spelling: str = "none"
    proper_names: dict[str, str] = field(default_factory=dict)
    published_variants: list[str] = field(default_factory=list)
    #: One budget for every checked cut, or a table of per-variant budgets.
    page_budget: int | dict[str, int] = 2
    variant_exemptions: dict[str, list[str]] = field(default_factory=dict)
    print_content_width: int = round((210 - 2 * 14) * 96 / 25.4)
    print_content_height: int = round((297 - 2 * 15) * 96 / 25.4)
    screen_width: int = 1280
    max_gap_months: int = 3
    gap_allowlist: dict[tuple[str, str], str] = field(default_factory=dict)
    shared_skill_keywords: list[str] = field(default_factory=list)
    required_fields: dict[str, list[str]] = field(default_factory=dict)
    date_format: str = "YYYY-MM"
    summary_sentences: int = 1
    summary_soft_max: int = 25
    summary_hard_max: int = 30
    highlight_soft_range: list[int] = field(default_factory=lambda: [10, 30])
    highlight_hard_range: list[int] = field(default_factory=lambda: [3, 40])
    location_pattern: str = r"[^,\s][^,]*, [^,\s][^,]*"
    codespell_ignore_words: list[str] = field(default_factory=list)


def date_pattern(fmt: str) -> re.Pattern[str]:
    patterns = {
        "YYYY": r"[0-9]{4}",
        "YYYY-MM": r"[0-9]{4}-(?:0[1-9]|1[0-2])",
        "YYYY-MM-DD": r"[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])",
    }
    if fmt not in patterns:
        raise ConfigError("date_format: choose YYYY, YYYY-MM or YYYY-MM-DD")
    return re.compile(patterns[fmt])


def load_config(path: Path = Path("resume-checks.toml")) -> CheckConfig:
    """A missing file selects defaults; an existing file is validated strictly."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    defaults = CheckConfig()
    known = {f.name for f in fields(defaults)}
    if "published_variant" in raw:
        raise ConfigError(
            "published_variant: replaced in 0.2.0 by published_variants, "
            'a list of names (e.g. published_variants = ["one-page"])'
        )
    if unknown := raw.keys() - known:
        raise ConfigError(f"unknown checks key(s): {', '.join(sorted(unknown))}")
    for key, value in raw.items():
        default = getattr(defaults, key)
        if key == "page_budget" and isinstance(value, dict):
            if not value or any(type(v) is not int or v <= 0 for v in value.values()):
                raise ConfigError(
                    "page_budget: expected a positive integer, or a table of "
                    'variant = positive integer (e.g. { "2-page" = 2 })'
                )
            continue
        if type(value) is not type(default):
            raise ConfigError(f"{key}: expected {type(default).__name__}")
        if isinstance(default, int) and (
            value < 0 or (key != "max_gap_months" and value == 0)
        ):
            raise ConfigError(f"{key}: expected a positive integer")
        if isinstance(default, list):
            element = int if key.endswith("_range") else str
            if any(type(v) is not element for v in value):
                raise ConfigError(f"{key}: expected a list of {element.__name__}")
            if element is int and (len(value) != 2 or not 1 <= value[0] <= value[1]):
                raise ConfigError(
                    f"{key}: expected [minimum, maximum], 1 <= minimum <= maximum"
                )
        if key == "proper_names" and any(
            not isinstance(v, str) or not k or not v for k, v in value.items()
        ):
            raise ConfigError(
                "proper_names: expected non-empty wrong = correct strings"
            )
        if key == "required_fields" and any(
            not isinstance(v, list) or any(not isinstance(f, str) or not f for f in v)
            for v in value.values()
        ):
            raise ConfigError("required_fields: expected section = [field names]")
        if key == "variant_exemptions" and any(
            not isinstance(v, list) or any(r not in VARIANT_RULES for r in v)
            for v in value.values()
        ):
            raise ConfigError(
                "variant_exemptions: expected variant = [rule names] among "
                + ", ".join(sorted(VARIANT_RULES))
            )
    gaps = {}
    for bounds, reason in raw.get("gap_allowlist", {}).items():
        parts = bounds.split("..")
        if (
            len(parts) != 2
            or any(not date_pattern("YYYY-MM").fullmatch(p) for p in parts)
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ConfigError(
                "gap_allowlist: expected 'YYYY-MM..YYYY-MM' = non-empty reason"
            )
        if parts[0] >= parts[1]:
            raise ConfigError("gap_allowlist: end date must precede start date")
        gaps[tuple(parts)] = reason
    raw["gap_allowlist"] = gaps
    config = CheckConfig(**raw)
    if unknown := set(config.enabled) - set(RULES):
        raise ConfigError(f"enabled: unknown rules: {', '.join(sorted(unknown))}")
    if len(config.enabled) != len(set(config.enabled)):
        raise ConfigError("enabled: duplicate rule names")
    if config.spelling not in {"none", "en-GB"}:
        raise ConfigError("spelling: choose none or en-GB")
    date_pattern(config.date_format)
    try:
        re.compile(config.location_pattern)
    except re.error as exc:
        raise ConfigError(f"location_pattern: {exc}") from exc
    if config.summary_soft_max > config.summary_hard_max:
        raise ConfigError("summary_soft_max must not exceed summary_hard_max")
    if not (
        config.highlight_hard_range[0]
        <= config.highlight_soft_range[0]
        <= config.highlight_soft_range[1]
        <= config.highlight_hard_range[1]
    ):
        raise ConfigError("highlight_soft_range must fit inside highlight_hard_range")
    return config


def published_variants(
    config: CheckConfig, variants: dict[str, Variant]
) -> list[Variant]:
    """The cuts that variant rules check, in variants.toml order.

    An explicit `published_variants` list wins; otherwise every `publish = true`
    variant, or the whole document when nothing is published. Names in
    `published_variants`, `variant_exemptions` and a page-budget table must
    exist in variants.toml, so a renamed variant cannot silently drop a check.
    """
    for key, names in (
        ("published_variants", config.published_variants),
        ("variant_exemptions", config.variant_exemptions),
        (
            "page_budget",
            config.page_budget if isinstance(config.page_budget, dict) else {},
        ),
    ):
        if missing := [name for name in names if name not in variants]:
            raise ConfigError(
                f"{key}: {', '.join(map(repr, missing))} not in variants.toml; "
                f"it defines: {', '.join(variants) or '(none)'}"
            )
    if config.published_variants:
        return [variants[name] for name in config.published_variants]
    return [v for v in variants.values() if v.publish] or [
        Variant("all", "", frozenset({"*"}))
    ]


def checked_variants(
    rule: str, config: CheckConfig, variants: dict[str, Variant]
) -> list[Variant]:
    """The published cuts `rule` applies to, minus configured exemptions."""
    return [
        v
        for v in published_variants(config, variants)
        if rule not in config.variant_exemptions.get(v.name, [])
    ]


def page_budget_for(config: CheckConfig, variant: str) -> int | None:
    """A scalar budget binds every cut; a table binds only the cuts it names."""
    if isinstance(config.page_budget, dict):
        return config.page_budget.get(variant)
    return config.page_budget
