"""Tag-based filtering of resume content into variants.

Entries in resume.json may carry an `x-tags` list. The `x-` prefix marks it as a
local extension: the JSON Resume schema sets additionalProperties: true, so the
file still validates as a standard JSON Resume and stays readable by any other
tool in the ecosystem.

Bullets are the one place the schema forbids that trick: `highlights` items are
plain strings, so a tag cannot ride inside one. The `x-highlights` extension
covers it from the entry level instead — a mapping from a substring of a bullet
to that bullet's tags:

    {"highlights": ["Shipped X.", "Led Y."], "x-highlights": {"Led Y": ["full"]}}

The substring must match exactly one bullet, and the build fails loudly when an
edit breaks that match — a rule that silently stopped matching would silently
republish the bullet everywhere.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .paths import VARIANTS_TOML

TAG_KEY = "x-tags"
HIGHLIGHT_TAG_KEY = "x-highlights"
WILDCARD = "*"

#: Top-level keys holding lists of taggable entries.
TAGGABLE_SECTIONS = (
    "work",
    "volunteer",
    "education",
    "awards",
    "certificates",
    "publications",
    "skills",
    "languages",
    "interests",
    "references",
    "projects",
)


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    include: frozenset[str]
    #: Whether `resume site` puts this cut on the public GitHub Pages page.
    #: Defaults to False so a new variant — typically a CV tailored to one
    #: employer — is never published by accident. Publishing is opt-in.
    publish: bool = False
    style: dict[str, str] = field(default_factory=dict)

    @property
    def includes_everything(self) -> bool:
        return WILDCARD in self.include


class UnknownVariant(Exception):
    pass


class BadHighlightPattern(Exception):
    """An `x-highlights` substring matches zero or several bullets."""


def load_variants(path: Path = VARIANTS_TOML) -> dict[str, Variant]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    variants = {}
    for name, body in raw.items():
        if not isinstance(body, dict):
            raise ValueError(f"variant {name}: expected a table")
        unknown = body.keys() - {"description", "include", "publish", "style"}
        if unknown:
            raise ValueError(
                f"variant {name}: unknown keys: {', '.join(sorted(unknown))}"
            )
        if not isinstance(body.get("description", ""), str):
            raise ValueError(f"variant {name}.description: expected a string")
        include = body.get("include", [])
        if not isinstance(include, list) or any(
            not isinstance(t, str) for t in include
        ):
            raise ValueError(f"variant {name}.include: expected a list of strings")
        if not isinstance(body.get("publish", False), bool):
            raise ValueError(f"variant {name}.publish: expected a boolean")
        style = body.get("style", {})
        validate_style(style, where=f"variant {name}.style")
        variants[name] = Variant(
            name=name,
            description=body.get("description", ""),
            include=frozenset(include),
            publish=body.get("publish", False),
            style=style,
        )
    return variants


def validate_style(style: dict[str, str], *, where: str = "style") -> None:
    """Reject declarations that could escape the variant's custom properties."""
    if not isinstance(style, dict):
        raise ValueError(f"{where}: expected a table of CSS custom properties")
    for key, value in style.items():
        if not re.fullmatch(r"--[a-zA-Z_][a-zA-Z0-9_-]*", key):
            raise ValueError(f"{where}: {key!r} must be a CSS custom property")
        if (
            not isinstance(value, str)
            or not value.strip()
            or any(c in value for c in ";{}<\\")
            or "/*" in value
            or any(ord(c) < 32 for c in value)
        ):
            raise ValueError(f"{where}.{key}: expected a nonempty, safe CSS value")


def get_variant(name: str, path: Path = VARIANTS_TOML) -> Variant:
    variants = load_variants(path)
    if name not in variants:
        known = ", ".join(sorted(variants)) or "(none defined)"
        raise UnknownVariant(
            f"unknown variant {name!r}; variants.toml defines: {known}"
        )
    return variants[name]


def _keeps(entry: dict, variant: Variant) -> bool:
    tags = entry.get(TAG_KEY)
    if not tags:
        # Untagged content is core content: it appears in every variant.
        return True
    if variant.includes_everything:
        return True
    return bool(set(tags) & variant.include)


def _strip_tags(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k not in (TAG_KEY, HIGHLIGHT_TAG_KEY)}


def _filter_highlights(entry: dict, variant: Variant) -> dict:
    """Drop the bullets whose `x-highlights` tags the variant does not keep."""
    rules = entry.get(HIGHLIGHT_TAG_KEY)
    if not rules:
        return entry
    highlights = entry.get("highlights") or []
    tags_by_index: dict[int, list] = {}
    for pattern, tags in rules.items():
        matches = [i for i, h in enumerate(highlights) if pattern in h]
        if len(matches) != 1:
            position = entry.get("position", entry.get("title", "?"))
            where = f"{entry.get('name', '?')} — {position}"
            raise BadHighlightPattern(
                f"x-highlights pattern {pattern!r} in {where!r} matches "
                f"{len(matches)} bullets; it must match exactly one — "
                "make the substring unique, or update it to follow the bullet's edit"
            )
        tags_by_index[matches[0]] = tags
    kept = [
        h
        for i, h in enumerate(highlights)
        if i not in tags_by_index or _keeps({TAG_KEY: tags_by_index[i]}, variant)
    ]
    return {**entry, "highlights": kept}


def apply_variant(resume: dict, variant: Variant) -> dict:
    """Return a copy of `resume` holding only the entries `variant` selects.

    Bullets tagged via `x-highlights` are filtered the same way entries are.
    `x-tags` and `x-highlights` are stripped from the result so themes never
    have to know that variants exist.
    """
    out = dict(resume)
    for section in TAGGABLE_SECTIONS:
        entries = resume.get(section)
        if not isinstance(entries, list):
            continue
        kept = [
            _strip_tags(_filter_highlights(e, variant))
            for e in entries
            if isinstance(e, dict) and _keeps(e, variant)
        ]
        if kept:
            out[section] = kept
        else:
            # An emptied section should vanish rather than render as a bare heading.
            out.pop(section, None)
    return out
