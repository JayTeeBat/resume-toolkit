"""Config-driven quality checks, independent of any particular CV."""

from collections.abc import Callable
from pathlib import Path

from ..variants import Variant
from . import external, prose, structure
from .common import Violation
from .config import CheckConfig, published_variant

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
        prose.quantified,
        prose.lengths,
        structure.highlights,
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
    if set(config.enabled) & {"quantified", "page_budget", "header"}:
        published_variant(config, variants)
    violations = []
    invalid_dates = structure.dates(resume, config, variants)
    for name in config.enabled:
        if fast and name in {"page_budget", "header"}:
            continue
        if name in {"chronology", "overlaps", "gaps"} and invalid_dates:
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
    return violations
