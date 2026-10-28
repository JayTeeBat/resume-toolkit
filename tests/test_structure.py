"""Structural consistency gates for resume.json.

test_validate proves the document matches the schema and test_prose gates
the writing; these tests gate the shape the schema cannot express: every
role carries bullets, locations share one format, variant tags point at a
real cut, and the work history reads as one ordered, gap-accounted
timeline. Same contract as test_prose: rules are data, failures say where,
what, and what to write instead, and nothing is auto-fixed.
"""

from __future__ import annotations

import re
from itertools import combinations, pairwise

import pytest

from resume_toolkit.model import load_resume
from resume_toolkit.variants import (
    HIGHLIGHT_TAG_KEY,
    TAG_KEY,
    TAGGABLE_SECTIONS,
    WILDCARD,
    load_variants,
)
from test_prose import Violation, entry_label, fail_with

# --- rule data ---------------------------------------------------------------

# "City, Country": exactly one comma. Regions and counties are dropped so
# every entry reads the same way ("London, United Kingdom").
WORK_LOCATION_PATTERN = re.compile(r"[^,\s][^,]*, [^,\s][^,]*")

# Months of unexplained time between two consecutive roles that a reader
# will let pass without wondering what happened.
MAX_GAP_MONTHS = 3

# Gaps longer than MAX_GAP_MONTHS that are known and accepted, keyed by the
# (endDate, startDate) pair that bounds them. An entry that stops matching a
# gap fails the gate, so this list cannot rot.
GAP_ALLOWLIST = {
    # Employer F (ends 1843-02) → Employer E (starts 1843-09), 7 months.
    # Pending the owner's decision on how to account for it.
    ("1843-02", "1843-09"): "Employer F → Employer E",
}


# --- helpers -----------------------------------------------------------------


@pytest.fixture(scope="module")
def resume() -> dict:
    return load_resume()


def month_index(date: str, *, end: bool = False) -> int:
    """Months since year 0 for a schema date ("2010", "2010-08", "2010-08-31").

    A bare year spans the whole year: January as a start, December as an end.
    """
    parts = date.split("-")
    month = int(parts[1]) if len(parts) > 1 else (12 if end else 1)
    return int(parts[0]) * 12 + month - 1


def end_index(entry: dict) -> float:
    """An entry with no endDate is the current role: it runs forever."""
    return month_index(entry["endDate"], end=True) if "endDate" in entry else float("inf")


def on_or_after(date: str, reference: str) -> bool:
    """Compare two ISO dates at the coarser of their two precisions.

    A bare-year education endDate ("2010") does not say which month the
    diploma ended, so every role starting that year counts as on/after it.
    """
    n = min(len(date), len(reference))
    return date[:n] >= reference[:n]


def span(entry: dict) -> str:
    return f"{entry['startDate']}–{entry.get('endDate', 'present')}"


def section_label(section: str, entry: dict) -> str:
    if section == "work":
        return entry_label(entry)
    return entry.get("name") or entry.get("institution") or "?"


# --- gates -------------------------------------------------------------------


def test_every_role_has_highlights(resume) -> None:
    violations = [
        Violation(
            f"$.work[{i}].highlights  ({entry_label(entry)})",
            entry.get("summary", "(no summary)"),
            "add at least one bullet — split a long summary into a one-sentence "
            "summary plus verb-led highlights carrying the same facts",
        )
        for i, entry in enumerate(resume["work"])
        if not any(h.strip() for h in entry.get("highlights", []))
    ]
    fail_with("role without highlights", violations)


def test_work_locations_read_city_country(resume) -> None:
    violations = []
    for i, entry in enumerate(resume["work"]):
        location = entry.get("location", "")
        if WORK_LOCATION_PATTERN.fullmatch(location):
            continue
        parts = [p.strip() for p in location.split(",")]
        fix = (
            f'write "{parts[0]}, {parts[-1]}" — drop the region'
            if len(parts) > 2
            else 'write "City, Country"'
        )
        violations.append(Violation(f"$.work[{i}].location  ({entry_label(entry)})", location, fix))
    fail_with("work location is not City, Country", violations)


def test_tags_name_a_real_variant(resume) -> None:
    """A tag no variant knows is dead weight at best, and at worst a cut
    someone believes exists. Valid: a variant name, or a tag some variant
    lists in `include` (the wildcard is a selector, not a tag).
    """
    variants = load_variants()
    known = (set(variants) | {t for v in variants.values() for t in v.include}) - {WILDCARD}
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
                    f'remove "{tag}", or define it in variants.toml — known tags: {known_list}',
                )
                for where, tags in tagged
                for tag in tags
                if tag not in known
            ]
    fail_with("tag matches no variant", violations)


def test_work_is_reverse_chronological(resume) -> None:
    work = list(enumerate(resume["work"]))
    violations = [
        Violation(
            f"$.work[{j}]  ({entry_label(later)})",
            span(later),
            f"move it above $.work[{i}] ({entry_label(earlier)}, {span(earlier)}) — newest role first",
        )
        for (i, earlier), (j, later) in pairwise(work)
        if month_index(later["startDate"]) > month_index(earlier["startDate"])
    ]
    fail_with("work out of order", violations)


def test_work_entries_do_not_overlap(resume) -> None:
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
        for (i, a), (j, b) in combinations(enumerate(resume["work"]), 2)
        if month_index(a["startDate"]) < end_index(b) and month_index(b["startDate"]) < end_index(a)
    ]
    fail_with("overlapping roles", violations)


def test_career_gaps_are_accounted_for(resume) -> None:
    """Only roles starting on/after the latest education endDate are judged:
    internships during school leave gaps that are not career gaps.
    """
    school_end = max(
        (e["endDate"] for e in resume["education"] if "endDate" in e),
        key=lambda d: month_index(d, end=True),
    )
    career = sorted(
        (
            (i, e)
            for i, e in enumerate(resume["work"])
            if on_or_after(e["startDate"], school_end)
        ),
        key=lambda pair: month_index(pair[1]["startDate"]),
        reverse=True,
    )
    violations = []
    used = set()
    for (i, newer), (j, older) in pairwise(career):
        if "endDate" not in older:
            continue  # an ongoing older role overlaps; that gate reports it
        gap = month_index(newer["startDate"]) - month_index(older["endDate"], end=True) - 1
        key = (older["endDate"], newer["startDate"])
        if gap <= MAX_GAP_MONTHS:
            continue
        if key in GAP_ALLOWLIST:
            used.add(key)
            continue
        violations.append(
            Violation(
                f"$.work[{j}] → $.work[{i}]  ({entry_label(older)} → {entry_label(newer)})",
                f"{older['endDate']} → {newer['startDate']}",
                f"{gap}-month gap (limit {MAX_GAP_MONTHS}) — add a role covering it, "
                f"or add {key!r} to GAP_ALLOWLIST with the reason",
            )
        )
    violations += [
        Violation(
            f"GAP_ALLOWLIST[{key!r}]",
            reason,
            f"no gap over {MAX_GAP_MONTHS} months is bounded by these dates any more — remove the entry",
        )
        for key, reason in GAP_ALLOWLIST.items()
        if key not in used
    ]
    fail_with("unaccounted career gap", violations)
