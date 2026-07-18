"""Prose quality gates for resume.json.

test_validate proves the document is well-formed; these tests gate the
writing itself. Every rule here is a mechanical check that a review pass
once fixed by hand: terminal punctuation, UK spelling, typography, tense
drift between current and past roles, and unquantified entries on the
published cut. Judgment calls (is this bullet vague?) stay with humans;
nothing in this file should ever need interpretation to stay green.

The rules are data-driven: extend the gate by extending the lists below.

There is deliberately no auto-fix, so a failure message must carry
everything needed to make the edit: which entry, the offending text, and
what to write instead. If locating a violation ever requires searching
resume.json by hand, that is a bug in this file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterator

import pytest

from resume_toolkit.build import build_variant
from resume_toolkit.model import load_resume
from resume_toolkit.paths import RESUME_JSON
from resume_toolkit.pdf import BrowserMissing
from resume_toolkit.variants import apply_variant, get_variant

REPO_ROOT = RESUME_JSON.parent

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
NON_PROSE_KEYS = {
    "$schema",
    "canonical",
    "countryCode",
    "email",
    "postalCode",
    "source",
    "url",
    "username",
    "x-highlights",
    "x-tags",
}

PUBLISHED_VARIANT = "short"


# --- violation reporting -----------------------------------------------------
#
# Every gate reports through fail_with(), one block per violation:
#
#     where:  $.work[0].highlights[1]  (Analytical Engines — Lead Engineer)
#     text:   "…engine notes for the research group (100+ pages)"
#     fix:    add a final period
#
# `where` is the JSON path plus, for work entries, the company and position,
# so the reader lands on the right entry without counting array indices.


class Violation:
    def __init__(self, where: str, text: str, fix: str) -> None:
        self.where = where
        self.text = text
        self.fix = fix

    def render(self) -> str:
        return f"  where:  {self.where}\n  text:   {clip(self.text)}\n  fix:    {self.fix}"


def fail_with(rule: str, violations: list[Violation]) -> None:
    if not violations:
        return
    blocks = "\n\n".join(v.render() for v in violations)
    pytest.fail(f"{rule} — {len(violations)} violation(s):\n\n{blocks}", pytrace=False)


def clip(text: str, width: int = 70) -> str:
    """Quote text for a failure message, eliding the middle of long strings."""
    if len(text) <= width:
        return f'"{text}"'
    head, tail = width // 2, width // 2
    return f'"{text[:head]}…{text[-tail:]}"'


def entry_label(entry: dict) -> str:
    return f"{entry.get('name', '?')} — {entry.get('position', '?')}"


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
    """Yield (where, text) for strings that must read as sentences."""
    yield "$.basics.summary", resume["basics"]["summary"]
    for i, entry in enumerate(resume["work"]):
        label = entry_label(entry)
        if "summary" in entry:
            yield f"$.work[{i}].summary  ({label})", entry["summary"]
        for j, highlight in enumerate(entry.get("highlights", [])):
            yield f"$.work[{i}].highlights[{j}]  ({label})", highlight


def first_word(text: str) -> str:
    match = re.match(r"[A-Za-z]+", text)
    return match.group() if match else ""


def match_context(text: str, match: re.Match[str], margin: int = 20) -> str:
    """The matched text with enough surrounding context to find it."""
    lo = max(0, match.start() - margin)
    hi = min(len(text), match.end() + margin)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi]}{suffix}"


# --- gates -------------------------------------------------------------------


def test_sentences_end_with_a_period(resume) -> None:
    violations = [
        Violation(where, text, "add a final period")
        for where, text in iter_sentences(resume)
        if not text.endswith(".")
    ]
    fail_with("end-of-sentence period missing", violations)


def test_no_us_spellings(resume) -> None:
    pattern = re.compile(r"\w*(?:" + "|".join(US_SPELLING_STEMS) + r")\w*", re.IGNORECASE)
    violations = [
        Violation(where, match_context(text, m), f'replace "{m.group()}" with its UK spelling')
        for where, text in iter_strings(resume)
        if (m := pattern.search(text))
    ]
    fail_with("US spelling in a UK-spelling document", violations)


def test_proper_names_are_cased_correctly(resume) -> None:
    violations = [
        Violation(where, text, f'write "{right}", not "{wrong}"')
        for where, text in iter_strings(resume)
        for wrong, right in CASING.items()
        if wrong in text
    ]
    fail_with("miscased proper name", violations)


def test_typography(resume) -> None:
    rules = (
        ("collapse the double space", re.compile(r"  ")),
        ("strip the leading/trailing whitespace", re.compile(r"^\s|\s$")),
        ("write an em dash (—), not a spaced hyphen", re.compile(r" - ")),
        ("write × for multiplication, not '*'", re.compile(r"\d\s*\*|\*\s*\d")),
        ("write × for multiplication, not the letter 'x'", re.compile(r"\d\s*x\s*\d")),
        ("put the currency symbol before the amount (€5, not 5€)", re.compile(r"\d\s*[€$£]")),
    )
    violations = [
        Violation(where, match_context(text, m), fix)
        for where, text in iter_strings(resume)
        for fix, pattern in rules
        if (m := pattern.search(text))
    ]
    fail_with("typography", violations)


def test_tense_matches_the_role(resume) -> None:
    """Current role (no endDate) opens bullets in the present; past roles in
    the past. Only verbs the lists recognise are judged, so noun-phrase
    summaries pass through unexamined — this catches drift, it does not prove
    completeness.
    """
    violations: list[Violation] = []
    for i, entry in enumerate(resume["work"]):
        current = "endDate" not in entry
        label = entry_label(entry)
        texts = [(f"$.work[{i}].summary  ({label})", entry["summary"])] if "summary" in entry else []
        texts += [
            (f"$.work[{i}].highlights[{j}]  ({label})", h)
            for j, h in enumerate(entry.get("highlights", []))
        ]
        for where, text in texts:
            word = first_word(text)
            looks_present = word in PRESENT_VERBS
            looks_past = word in IRREGULAR_PAST or word.endswith("ed")
            if current and looks_past and not looks_present:
                violations.append(
                    Violation(where, text, f'"{word}" is past tense — the current role reads in the present')
                )
            elif not current and looks_present and not looks_past:
                violations.append(
                    Violation(where, text, f'"{word}" is present tense — past roles read in the past')
                )
    fail_with("tense drift", violations)


def test_published_entries_are_quantified(resume) -> None:
    """Every work entry on the published cut carries at least one figure."""
    cut = apply_variant(resume, get_variant(PUBLISHED_VARIANT))
    violations = [
        Violation(
            f"$.work[{i}]  ({entry_label(entry)})",
            entry.get("summary", "(no summary)"),
            "add at least one concrete figure (scale, spec, cost, accuracy…) or tag the entry out of the published cut",
        )
        for i, entry in enumerate(cut["work"])
        if not any(
            c.isdigit() for c in entry.get("summary", "") + " ".join(entry.get("highlights", []))
        )
    ]
    fail_with("published entry has no figure at all", violations)


def test_no_typos_anywhere_codespell() -> None:
    """The one class the UK-consistency list cannot catch: plain misspellings
    ('resouces' shipped once). codespell sweeps the whole repo; skips and
    proper-noun exceptions live in [tool.codespell] in pyproject.toml.
    """
    codespell = shutil.which("codespell")
    assert codespell, "codespell missing from the venv — run `uv sync`"
    result = subprocess.run(
        [codespell, "."], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        "codespell found typos (real typo: fix the file; proper noun: add it "
        f"to ignore-words-list in pyproject.toml):\n{result.stdout}"
    )


@pytest.mark.slow
def test_published_variant_stays_within_two_pages(resume, tmp_path) -> None:
    """The published cut's page budget is 2. One page stopped being realistic
    once the CV settled on quantified bullets for every role; two is still a
    deliberate limit a recruiter will tolerate — content growth has to be paid
    for by trimming elsewhere, not by a third page.
    """
    from pypdf import PdfReader

    try:
        written = build_variant(
            resume, get_variant(PUBLISHED_VARIANT), formats=("pdf",), out_dir=tmp_path
        )
    except BrowserMissing:
        pytest.skip("Chromium not installed; run `playwright install chromium`")
    pages = len(PdfReader(written[0].path).pages)
    assert pages <= 2, (
        f"the published '{PUBLISHED_VARIANT}' cut renders to {pages} pages; the budget is 2 — "
        "trim or tag entries out of the cut (x-tags), or tighten the theme's "
        "spacing tokens (--size-base, --leading, --section-gap)"
    )
