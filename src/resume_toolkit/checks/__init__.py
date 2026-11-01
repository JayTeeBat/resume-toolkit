"""Config-driven quality checks, independent of any particular CV."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from ..variants import Variant
from . import external, prose, structure
from .common import Violation
from .config import BROWSER_RULES, VARIANT_RULES, CheckConfig, published_variants

Rule = Callable[[dict, CheckConfig, dict[str, Variant]], list[Violation]]
RULE_FUNCTIONS: dict[str, Rule] = {
    rule.__name__: rule
    for rule in (
        prose.punctuation,
        prose.spelling,
        prose.proper_names,
        prose.typography,
        prose.unit_spacing,
        prose.tense,
        prose.verb_led,
        prose.weak_phrases,
        prose.skill_evidence,
        prose.quantified,
        prose.lengths,
        structure.highlights,
        structure.required_sections,
        structure.role_highlights,
        structure.locations,
        structure.tags,
        structure.chronology,
        structure.overlaps,
        structure.gaps,
        structure.skills,
        structure.required_fields,
        structure.dates,
        external.page_budget,
        external.header,
        external.page_breaks,
    )
}


def run_checks(
    resume: dict,
    config: CheckConfig,
    variants: dict[str, Variant],
    *,
    fast: bool = False,
    root: Path = Path("."),
) -> list[Violation]:
    """Run in configured order; invalid dates block only timeline comparisons."""
    if set(config.enabled) & VARIANT_RULES:
        published_variants(config, variants)
    violations = []
    invalid_dates = structure.dates(resume, config, variants)
    for name in config.enabled:
        if fast and name in BROWSER_RULES:
            continue
        if (
            name in {"chronology", "overlaps", "gaps", "role_highlights"}
            and invalid_dates
        ):
            # Keep prerequisites visible even if the date rule was disabled.
            if "dates" not in config.enabled and not any(
                v.rule == "dates" for v in violations
            ):
                violations.extend(invalid_dates)
            continue
        if name == "codespell":
            violations.extend(external.codespell(root, config))
        else:
            violations.extend(RULE_FUNCTIONS[name](resume, config, variants))
    return [
        replace(v, severity=config.severity.get(v.rule, v.severity)) for v in violations
    ]
