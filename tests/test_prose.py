"""Prose quality gates for resume.json.

test_validate proves the document is well-formed; these tests gate the
writing itself. Every rule here is a mechanical check that a review pass
once fixed by hand: terminal punctuation, UK spelling, typography, tense
drift between current and past roles, and unquantified entries on the
public one-pager. Judgment calls (is this bullet vague?) stay with humans;
nothing in this file should ever need interpretation to stay green.

The rules are data-driven: extend the gate by extending the lists below.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest

from resume_toolkit.build import build_variant
from resume_toolkit.model import load_resume
from resume_toolkit.pdf import BrowserMissing
from resume_toolkit.variants import apply_variant, get_variant

# --- rule data ---------------------------------------------------------------

# US spellings (stems, matched case-insensitively). Small on purpose: this
# enforces *consistency* with the UK spelling the CV settled on, not general
# orthography — a stem only belongs here once the UK form is the one in use.
US_SPELLING_STEMS = (
    "analyz",
    "behavior",
    "characteriz",
    "color",
    "customiz",
    "maximiz",
    "minimiz",
    "modeling",
    "optimiz",
    "organiz",
    "prioritiz",
    "standardiz",
    "summariz",
    "utiliz",
    "visualiz",
)

# Exact spellings for names that have one true casing.
CASING = {
    "Github": "GitHub",
    "Gitlab": "GitLab",
    "Linkedin": "LinkedIn",
    "Mongodb": "MongoDB",
    "Fastapi": "FastAPI",
}

# Verbs that open a bullet in the imperative/present. Only unambiguous verb
# forms belong here — "Design" or "Research" read as nouns at the head of a
# noun phrase and would flag correct sentences.
PRESENT_VERBS = {
    "Build",
    "Create",
    "Define",
    "Deliver",
    "Develop",
    "Drive",
    "Enforce",
    "Fix",
    "Implement",
    "Lead",
    "Maintain",
    "Manage",
    "Own",
    "Run",
    "Set",
    "Ship",
    "Specify",
    "Turn",
    "Write",
}

# Past forms that don't end in "-ed".
IRREGULAR_PAST = {
    "Built",
    "Brought",
    "Held",
    "Kept",
    "Led",
    "Made",
    "Ran",
    "Set",
    "Took",
    "Won",
    "Wrote",
}

# Keys whose values are identifiers, not prose.
NON_PROSE_KEYS = {"$schema", "canonical", "countryCode", "email", "postalCode", "url", "username"}

PUBLISHED_VARIANT = "short"


# --- helpers -----------------------------------------------------------------


@pytest.fixture(scope="module")
def resume() -> dict:
    return load_resume()


def iter_strings(node, path: str = "$") -> Iterator[tuple[str, str]]:
    """Yield (json_path, text) for every prose string in the document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key not in NON_PROSE_KEYS:
                yield from iter_strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from iter_strings(value, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def iter_sentences(resume: dict) -> Iterator[tuple[str, str]]:
    """Yield (json_path, text) for strings that must read as sentences."""
    yield "$.basics.summary", resume["basics"]["summary"]
    for i, entry in enumerate(resume["work"]):
        if "summary" in entry:
            yield f"$.work[{i}].summary", entry["summary"]
        for j, highlight in enumerate(entry.get("highlights", [])):
            yield f"$.work[{i}].highlights[{j}]", highlight


def first_word(text: str) -> str:
    match = re.match(r"[A-Za-z]+", text)
    return match.group() if match else ""


# --- gates -------------------------------------------------------------------


def test_sentences_end_with_a_period(resume) -> None:
    missing = [path for path, text in iter_sentences(resume) if not text.endswith(".")]
    assert not missing, f"sentences without a terminal period: {missing}"


def test_no_us_spellings(resume) -> None:
    pattern = re.compile("|".join(US_SPELLING_STEMS), re.IGNORECASE)
    hits = [
        (path, match.group())
        for path, text in iter_strings(resume)
        if (match := pattern.search(text))
    ]
    assert not hits, f"US spellings in a UK-spelling document: {hits}"


def test_proper_names_are_cased_correctly(resume) -> None:
    hits = [
        (path, wrong)
        for path, text in iter_strings(resume)
        for wrong in CASING
        if wrong in text
    ]
    assert not hits, f"miscased names (see CASING for the true form): {hits}"


def test_typography(resume) -> None:
    rules = (
        ("double space", re.compile(r"  ")),
        ("stray leading/trailing whitespace", re.compile(r"^\s|\s$")),
        ("'*' as a multiplication sign (use ×)", re.compile(r"\d\s*\*|\*\s*\d")),
        ("letter 'x' as a multiplication sign (use ×)", re.compile(r"\d\s*x\s*\d")),
        ("currency symbol after the amount (write €5, not 5€)", re.compile(r"\d\s*[€$£]")),
    )
    hits = [
        (path, why)
        for path, text in iter_strings(resume)
        for why, pattern in rules
        if pattern.search(text)
    ]
    assert not hits, f"typography violations: {hits}"


def test_tense_matches_the_role(resume) -> None:
    """Current role (no endDate) opens bullets in the present; past roles in
    the past. Only verbs the lists recognise are judged, so noun-phrase
    summaries pass through unexamined — this catches drift, it does not prove
    completeness.
    """
    wrong: list[tuple[str, str]] = []
    for i, entry in enumerate(resume["work"]):
        current = "endDate" not in entry
        texts = [(f"$.work[{i}].summary", entry["summary"])] if "summary" in entry else []
        texts += [
            (f"$.work[{i}].highlights[{j}]", h) for j, h in enumerate(entry.get("highlights", []))
        ]
        for path, text in texts:
            word = first_word(text)
            looks_present = word in PRESENT_VERBS
            looks_past = word in IRREGULAR_PAST or word.endswith("ed")
            if current and looks_past and not looks_present:
                wrong.append((path, f"'{word}' is past tense in the current role"))
            elif not current and looks_present and not looks_past:
                wrong.append((path, f"'{word}' is present tense in a past role"))
    assert not wrong, f"tense drift: {wrong}"


def test_published_entries_are_quantified(resume) -> None:
    """Every work entry on the public one-pager carries at least one figure."""
    cut = apply_variant(resume, get_variant(PUBLISHED_VARIANT))
    unquantified = [
        f"$.work[{i}] ({entry['name']} — {entry['position']})"
        for i, entry in enumerate(cut["work"])
        if not any(c.isdigit() for c in entry.get("summary", "") + " ".join(entry.get("highlights", [])))
    ]
    assert not unquantified, f"published entries without a single figure: {unquantified}"


@pytest.mark.slow
@pytest.mark.xfail(reason="short is 2 pages until the skills consolidation lands", strict=True)
def test_published_variant_fits_one_page(resume, tmp_path) -> None:
    from pypdf import PdfReader

    try:
        written = build_variant(
            resume, get_variant(PUBLISHED_VARIANT), formats=("pdf",), out_dir=tmp_path
        )
    except BrowserMissing:
        pytest.skip("Chromium not installed; run `playwright install chromium`")
    assert len(PdfReader(written[0].path).pages) == 1
