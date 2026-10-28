"""Generic prose rules; each returns actionable violations."""

from __future__ import annotations

import re
from dataclasses import replace

from ..variants import (
    Variant,
    apply_variant,
)
from .common import (
    Violation,
    entry_label,
    finish,
    first_word,
    iter_sentences,
    iter_strings,
    looks_past,
    looks_present,
    match_context,
)
from .config import CheckConfig, published_variant
from .language import SENTENCE_END, UNIT_WITHOUT_SPACE, US_SPELLING_STEMS


def punctuation(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = [
        Violation(where, text, "add a final period")
        for where, text in iter_sentences(resume)
        if not text.endswith(".")
    ]
    return finish("punctuation", violations)


def spelling(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    if config.spelling == "none":
        return []
    pattern = re.compile(
        r"\w*(?:" + "|".join(US_SPELLING_STEMS) + r")\w*", re.IGNORECASE
    )
    violations = [
        Violation(
            where, match_context(text, m), f'replace "{m.group()}" with its UK spelling'
        )
        for where, text in iter_strings(resume)
        if (m := pattern.search(text))
    ]
    return finish("spelling", violations)


def proper_names(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = [
        Violation(where, text, f'write "{right}", not "{wrong}"')
        for where, text in iter_strings(resume)
        for wrong, right in config.proper_names.items()
        if wrong in text
    ]
    return finish("proper_names", violations)


def typography(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    rules = (
        ("collapse the double space", re.compile(r"  ")),
        ("strip the leading/trailing whitespace", re.compile(r"^\s|\s$")),
        ("write an em dash (—), not a spaced hyphen", re.compile(r" - ")),
        ("write × for multiplication, not '*'", re.compile(r"\d\s*\*|\*\s*\d")),
        ("write × for multiplication, not the letter 'x'", re.compile(r"\d\s*x\s*\d")),
        (
            "put the currency symbol before the amount (€5, not 5€)",
            re.compile(r"\d\s*[€$£]"),
        ),
    )
    violations = [
        Violation(where, match_context(text, m), fix)
        for where, text in iter_strings(resume)
        for fix, pattern in rules
        if (m := pattern.search(text))
    ]
    return finish("typography", violations)


def unit_spacing(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = [
        Violation(
            where,
            match_context(text, match),
            f'insert whitespace: write "{match.group("number")} {match.group("unit")}"',
        )
        for where, text in iter_strings(resume)
        for match in UNIT_WITHOUT_SPACE.finditer(text)
    ]
    return finish("unit_spacing", violations)


def tense(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    """Current role (no endDate) opens bullets in the present; past roles in
    the past. Only verbs the lists recognise are judged, so noun-phrase
    summaries pass through unexamined — this catches drift, it does not prove
    completeness.
    """
    violations: list[Violation] = []
    for i, entry in enumerate(resume.get("work", [])):
        current = "endDate" not in entry
        label = entry_label(entry)
        texts = (
            [(f"$.work[{i}].summary  ({label})", entry["summary"])]
            if "summary" in entry
            else []
        )
        texts += [
            (f"$.work[{i}].highlights[{j}]  ({label})", h)
            for j, h in enumerate(entry.get("highlights", []))
        ]
        for where, text in texts:
            word = first_word(text)
            present, past = looks_present(word), looks_past(word)
            if current and past and not present:
                violations.append(
                    Violation(
                        where,
                        text,
                        f'"{word}" is past tense — the current '
                        f"role reads in the present",
                    )
                )
            elif not current and present and not past:
                violations.append(
                    Violation(
                        where,
                        text,
                        f'"{word}" is present tense — past roles read in the past',
                    )
                )
    return finish("tense", violations)


def verb_led(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    """A bullet states what was done, so it opens on a verb the tense lists
    recognise: "Characterised the layers", not "Characterisation of the
    layers". A genuine verb missing from the lists belongs in PRESENT_VERBS
    or IRREGULAR_PAST, not in an exception here.
    """
    violations = []
    for i, entry in enumerate(resume.get("work", [])):
        tense = (
            "present (Build, Lead…)" if "endDate" not in entry else "past (Built, Led…)"
        )
        for j, text in enumerate(entry.get("highlights", [])):
            word = first_word(text)
            if not (looks_present(word) or looks_past(word)):
                violations.append(
                    Violation(
                        f"$.work[{i}].highlights[{j}]  ({entry_label(entry)})",
                        text,
                        f'"{word}" is not a recognised verb — open '
                        f"with a verb in the {tense}",
                    )
                )
    return finish("verb_led", violations)


def quantified(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    """Every work entry on the published cut carries at least one figure."""
    cut = apply_variant(resume, published_variant(config, variants))
    violations = [
        Violation(
            f"$.work[{i}]  ({entry_label(entry)})",
            entry.get("summary", "(no summary)"),
            "add at least one concrete figure (scale, spec, cost, "
            "accuracy…) or tag the entry out of the published cut",
        )
        for i, entry in enumerate(cut.get("work", []))
        if not any(
            c.isdigit()
            for c in entry.get("summary", "") + " ".join(entry.get("highlights", []))
        )
    ]
    return finish("quantified", violations)


def lengths(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = []
    for where, text in iter_sentences(resume):
        if not where.startswith("$.work["):
            continue
        summary = ".summary " in where
        words = len(text.split())
        if summary:
            sentences = len(SENTENCE_END.findall(text))
            if sentences != config.summary_sentences or not text.rstrip().endswith(
                (".", "!", "?")
            ):
                violations.append(
                    Violation(
                        where,
                        text,
                        f"write exactly {config.summary_sentences} "
                        f"sentence (found {sentences} sentence endings)",
                    )
                )
        hard_min, hard_max = (
            (1, config.summary_hard_max) if summary else config.highlight_hard_range
        )
        soft_min, soft_max = (
            (1, config.summary_soft_max) if summary else config.highlight_soft_range
        )
        if not hard_min <= words <= hard_max:
            violations.append(
                Violation(
                    where,
                    text,
                    f"rewrite within {hard_min}–{hard_max} words "
                    f"(hard limit; found {words})",
                )
            )
        elif not soft_min <= words <= soft_max:
            violation = Violation(
                where,
                text,
                f"aim for {soft_min}–{soft_max} words (found "
                f"{words}), or justify keeping this wording",
            )
            violations.append(replace(violation, severity="soft"))
    return finish("lengths", violations)
