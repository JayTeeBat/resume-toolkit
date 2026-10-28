"""Violations always say where, what, and what to write instead; no auto-fix."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Literal

from .language import IRREGULAR_PAST, NON_PROSE_KEYS, PRESENT_VERBS


@dataclass(frozen=True)
class Violation:
    where: str
    text: str
    fix: str
    rule: str = ""
    severity: Literal["hard", "soft"] = "hard"

    def render(self) -> str:
        return (
            f"  where:  {self.where}\n  text:   {clip(self.text)}\n  fix:    {self.fix}"
        )


def finish(rule: str, violations: list[Violation]) -> list[Violation]:
    return [replace(v, rule=rule) for v in violations]


def clip(text: str, width: int = 70) -> str:
    """Quote text for a failure message, eliding the middle of long strings."""
    if len(text) <= width:
        return f'"{text}"'
    head, tail = width // 2, width // 2
    return f'"{text[:head]}…{text[-tail:]}"'


def entry_label(entry: dict) -> str:
    return f"{entry.get('name', '?')} — {entry.get('position', '?')}"


def iter_strings(node: object, path: str = "$") -> Iterator[tuple[str, str]]:
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
    if resume.get("basics", {}).get("summary"):
        yield "$.basics.summary", resume["basics"]["summary"]
    for i, entry in enumerate(resume.get("work", [])):
        label = entry_label(entry)
        if "summary" in entry:
            yield f"$.work[{i}].summary  ({label})", entry["summary"]
        for j, highlight in enumerate(entry.get("highlights", [])):
            yield f"$.work[{i}].highlights[{j}]  ({label})", highlight


def first_word(text: str) -> str:
    match = re.match(r"[A-Za-z]+", text)
    return match.group() if match else ""


def looks_present(word: str) -> bool:
    return word in PRESENT_VERBS


def looks_past(word: str) -> bool:
    return word in IRREGULAR_PAST or word.endswith("ed")


def match_context(text: str, match: re.Match[str], margin: int = 20) -> str:
    """The matched text with enough surrounding context to find it."""
    lo = max(0, match.start() - margin)
    hi = min(len(text), match.end() + margin)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{text[lo:hi]}{suffix}"
