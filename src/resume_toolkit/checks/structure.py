"""Generic structure rules; each returns actionable violations."""

from __future__ import annotations

import re
from itertools import combinations, pairwise

from ..variants import (
    HIGHLIGHT_TAG_KEY,
    TAG_KEY,
    TAGGABLE_SECTIONS,
    WILDCARD,
    Variant,
)
from .common import (
    Violation,
    entry_label,
    finish,
)
from .config import CheckConfig, date_pattern

DATE_FIELDS = {"startDate", "endDate", "releaseDate", "date"}


def section_label(section: str, entry: dict) -> str:
    if section == "work":
        return entry_label(entry)
    return entry.get("name") or entry.get("institution") or "?"


def span(entry: dict) -> str:
    return f"{entry['startDate']}–{entry.get('endDate', 'present')}"


def end_index(entry: dict) -> float:
    """An entry with no endDate is the current role: it runs forever."""
    return month_index(entry["endDate"]) if "endDate" in entry else float("inf")


def month_index(date: str) -> int:
    """Months since year 0 for a YYYY-MM date."""
    parts = date.split("-")
    year, month = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
    return year * 12 + month - 1


def highlights(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = [
        Violation(
            f"$.work[{i}].highlights  ({entry_label(entry)})",
            entry.get("summary", "(no summary)"),
            "add at least one bullet — split a long summary into a one-sentence "
            "summary plus verb-led highlights carrying the same facts",
        )
        for i, entry in enumerate(resume.get("work", []))
        if not any(h.strip() for h in entry.get("highlights", []))
    ]
    return finish("highlights", violations)


def locations(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = []
    for i, entry in enumerate(resume.get("work", [])):
        location = entry.get("location", "")
        if re.compile(config.location_pattern).fullmatch(location):
            continue
        parts = [p.strip() for p in location.split(",")]
        fix = (
            f'write "{parts[0]}, {parts[-1]}" — drop the region'
            if len(parts) > 2
            else 'write "City, Country"'
        )
        if config.location_pattern != CheckConfig().location_pattern:
            fix = f"write a location matching {config.location_pattern!r}"
        violations.append(
            Violation(f"$.work[{i}].location  ({entry_label(entry)})", location, fix)
        )
    return finish("locations", violations)


def tags(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    """A tag no variant knows is dead weight at best, and at worst a cut
    someone believes exists. Valid: a variant name, or a tag some variant
    lists in `include` (the wildcard is a selector, not a tag).
    """
    known = (set(variants) | {t for v in variants.values() for t in v.include}) - {
        WILDCARD
    }
    known_list = ", ".join(sorted(known))
    violations = []
    for section in TAGGABLE_SECTIONS:
        for i, entry in enumerate(resume.get(section) or []):
            label = section_label(section, entry)
            tagged = [(f"$.{section}[{i}].{TAG_KEY}", entry.get(TAG_KEY, []))]
            tagged += [
                (f'$.{section}[{i}].{HIGHLIGHT_TAG_KEY}["{pattern}"]', tags)
                for pattern, tags in entry.get(HIGHLIGHT_TAG_KEY, {}).items()
            ]
            violations += [
                Violation(
                    f"{where}  ({label})",
                    tag,
                    f'remove "{tag}", or define it in '
                    f"variants.toml — known tags: {known_list}",
                )
                for where, tags in tagged
                for tag in tags
                if tag not in known
            ]
    return finish("tags", violations)


def chronology(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    work = list(enumerate(resume.get("work", [])))
    violations = [
        Violation(
            f"$.work[{j}]  ({entry_label(later)})",
            span(later),
            f"move it above $.work[{i}] ({entry_label(earlier)}, "
            f"{span(earlier)}) — newest role first",
        )
        for (i, earlier), (j, later) in pairwise(work)
        if month_index(later["startDate"]) > month_index(earlier["startDate"])
    ]
    return finish("chronology", violations)


def overlaps(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    """Months are inclusive, so ending and starting in the same month is a
    handover, not an overlap.
    """
    violations = [
        Violation(
            f"$.work[{j}]  ({entry_label(b)})",
            span(b),
            f"overlaps $.work[{i}] ({entry_label(a)}, {span(a)}) — correct the dates, "
            "or give the earlier role its endDate",
        )
        for (i, a), (j, b) in combinations(enumerate(resume.get("work", [])), 2)
        if month_index(a["startDate"]) < end_index(b)
        and month_index(b["startDate"]) < end_index(a)
    ]
    return finish("overlaps", violations)


def gaps(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    """Include roles ending after school, including internships that straddle
    graduation.
    Roles wholly during school do not create career gaps.
    """
    school_end = max(
        (e["endDate"] for e in resume.get("education", []) if "endDate" in e),
        key=month_index,
        default="0000-01",
    )
    career = sorted(
        (
            (i, e)
            for i, e in enumerate(resume.get("work", []))
            if end_index(e) > month_index(school_end)
        ),
        key=lambda pair: month_index(pair[1]["startDate"]),
        reverse=True,
    )
    violations = []
    used = set()
    for (i, newer), (j, older) in pairwise(career):
        if "endDate" not in older:
            continue  # an ongoing older role overlaps; that gate reports it
        gap = month_index(newer["startDate"]) - month_index(older["endDate"]) - 1
        key = tuple(
            f"{value // 12:04d}-{value % 12 + 1:02d}"
            for value in (
                month_index(older["endDate"]),
                month_index(newer["startDate"]),
            )
        )
        if gap <= config.max_gap_months:
            continue
        if key in config.gap_allowlist:
            used.add(key)
            continue
        violations.append(
            Violation(
                f"$.work[{j}] → $.work[{i}]  ({entry_label(older)} "
                f"→ {entry_label(newer)})",
                f"{older['endDate']} → {newer['startDate']}",
                f"{gap}-month gap (limit {config.max_gap_months}) — add a "
                f"role covering it, "
                f"or add {'..'.join(key)!r} to gap_allowlist "
                "in resume-checks.toml with the reason",
            )
        )
    violations += [
        Violation(
            f"gap_allowlist[{key!r}]",
            reason,
            f"no gap over {config.max_gap_months} months is bounded by "
            f"these dates any more — remove the entry",
        )
        for key, reason in config.gap_allowlist.items()
        if key not in used
    ]
    return finish("gaps", violations)


def skills(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    occurrences = {}
    for i, group in enumerate(resume.get("skills", [])):
        for j, keyword in enumerate(group.get("keywords", [])):
            occurrences.setdefault(keyword.casefold(), {})[i] = (
                f"$.skills[{i}].keywords[{j}]  ({group.get('name', '?')})",
                keyword,
            )
    shared = {word.casefold() for word in config.shared_skill_keywords}
    duplicated = {word for word, groups in occurrences.items() if len(groups) > 1}
    violations = [
        Violation(
            where,
            keyword,
            "keep this keyword in only one skills group — also appears in "
            + ", ".join(other for other, _ in groups.values() if other != where),
        )
        for word, groups in occurrences.items()
        if word in duplicated - shared
        for where, keyword in groups.values()
    ]
    violations += [
        Violation(
            "shared_skill_keywords",
            word,
            "no longer shared across groups — remove this allowlist entry",
        )
        for word in sorted(config.shared_skill_keywords)
        if word.casefold() not in duplicated
    ]
    return finish("skills", violations)


def required_fields(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = [
        Violation(
            f"$.{section}[{i}].{field}  ({section_label(section, entry)})",
            str(entry.get(field, "(missing)")),
            f"supply a non-empty {field} using owner-confirmed facts",
        )
        for section, fields in config.required_fields.items()
        for i, entry in enumerate(resume.get(section, []))
        for field in fields
        if not isinstance(entry.get(field), str) or not entry[field].strip()
    ]
    return finish("required_fields", violations)


def dates(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = []

    def walk(node: object, path: str = "$") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                where = f"{path}.{key}"
                if key in DATE_FIELDS and (
                    not isinstance(value, str)
                    or not date_pattern(config.date_format).fullmatch(value)
                ):
                    violations.append(
                        Violation(
                            where,
                            str(value),
                            f"write {config.date_format} with a valid month "
                            "(01–12), using owner-confirmed dates",
                        )
                    )
                walk(value, where)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")

    walk(resume)
    violations += [
        Violation(
            f"$.work[{i}].startDate",
            "(missing)",
            f"supply {config.date_format} using owner-confirmed dates",
        )
        for i, entry in enumerate(resume.get("work", []))
        if not entry.get("startDate")
    ]
    return finish("dates", violations)
