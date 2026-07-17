"""Tag-based filtering of resume content into variants.

Entries in resume.json may carry an `x-tags` list. The `x-` prefix marks it as a
local extension: the JSON Resume schema sets additionalProperties: true, so the
file still validates as a standard JSON Resume and stays readable by any other
tool in the ecosystem.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .paths import VARIANTS_TOML

TAG_KEY = "x-tags"
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

    @property
    def includes_everything(self) -> bool:
        return WILDCARD in self.include


class UnknownVariant(Exception):
    pass


def load_variants(path: Path = VARIANTS_TOML) -> dict[str, Variant]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return {
        name: Variant(
            name=name,
            description=body.get("description", ""),
            include=frozenset(body.get("include", [])),
            publish=bool(body.get("publish", False)),
        )
        for name, body in raw.items()
    }


def get_variant(name: str, path: Path = VARIANTS_TOML) -> Variant:
    variants = load_variants(path)
    if name not in variants:
        known = ", ".join(sorted(variants)) or "(none defined)"
        raise UnknownVariant(f"unknown variant {name!r}; variants.toml defines: {known}")
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
    return {k: v for k, v in entry.items() if k != TAG_KEY}


def apply_variant(resume: dict, variant: Variant) -> dict:
    """Return a copy of `resume` holding only the entries `variant` selects.

    `x-tags` is stripped from the result so themes never have to know that
    variants exist.
    """
    out = dict(resume)
    for section in TAGGABLE_SECTIONS:
        entries = resume.get(section)
        if not isinstance(entries, list):
            continue
        kept = [_strip_tags(e) for e in entries if isinstance(e, dict) and _keeps(e, variant)]
        if kept:
            out[section] = kept
        else:
            # An emptied section should vanish rather than render as a bare heading.
            out.pop(section, None)
    return out
