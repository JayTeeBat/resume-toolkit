"""Orchestration: resume.json + variant + theme -> files on disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import DIST_DIR
from .pdf import html_to_pdf
from .render import render_html, render_markdown
from .variants import Variant, apply_variant
from .version import build_stamp


@dataclass(frozen=True)
class Artifact:
    variant: str
    fmt: str
    path: Path


def build_variant(
    resume: dict,
    variant: Variant,
    *,
    theme: str = "classic",
    formats: tuple[str, ...] = ("pdf", "html"),
    out_dir: Path = DIST_DIR,
) -> list[Artifact]:
    """Render one variant to the requested formats. Returns what was written."""
    data = apply_variant(resume, variant)
    # Stamped once per variant, not per format, so the artifacts of the same
    # cut can never disagree about what they are.
    stamp = build_stamp()
    html = render_html(data, theme=theme, variant=variant.name, stamp=stamp)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Artifact] = []

    if "html" in formats:
        path = out_dir / f"resume-{variant.name}.html"
        path.write_text(html, encoding="utf-8")
        written.append(Artifact(variant.name, "html", path))

    if "pdf" in formats:
        path = out_dir / f"resume-{variant.name}.pdf"
        html_to_pdf(html, path)
        written.append(Artifact(variant.name, "pdf", path))

    if "json" in formats:
        # The machine-readable cut: exactly what the theme rendered — variant
        # filtering applied, x-tags/x-highlights stripped — so a consumer of
        # this file can never see content the matching PDF does not show. The
        # stamp lands in `meta` (schema-blessed fields), carrying the same
        # provenance the human formats print in the colophon.
        payload = data
        if stamp:
            meta = {**(data.get("meta") or {}), "version": stamp.version, "lastModified": stamp.modified}
            payload = {**data, "meta": meta}
        path = out_dir / f"resume-{variant.name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(Artifact(variant.name, "json", path))

    if "md" in formats:
        md = render_markdown(data, theme=theme, variant=variant.name, stamp=stamp)
        path = out_dir / f"resume-{variant.name}.md"
        path.write_text(md, encoding="utf-8")
        written.append(Artifact(variant.name, "md", path))

    return written
