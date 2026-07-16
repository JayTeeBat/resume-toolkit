"""Orchestration: resume.json + variant + theme -> files on disk."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import DIST_DIR
from .pdf import html_to_pdf
from .render import render_html
from .variants import Variant, apply_variant


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
    html = render_html(data, theme=theme)
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

    return written
