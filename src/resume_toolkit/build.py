"""Orchestration: resume.json + variant + theme -> files on disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .paths import DIST_DIR
from .pdf import document_metadata, html_to_pdf, pdf_filename
from .render import render_html, render_markdown, render_print_footer
from .variants import Variant, apply_variant
from .version import build_stamp


@dataclass(frozen=True)
class Artifact:
    variant: str
    fmt: str
    path: Path


def artifact_filename(
    fmt: str, name: str, variant: str, primary_variant: str | None = None
) -> str:
    """Where one format of one cut lands; the single naming rule for every output.

    The primary cut owns the unsuffixed addresses — `resume.html`,
    `resume.json`, `resume.md` and `<Name>-Resume.pdf` — so its public URLs
    survive renaming the variant behind them. Every other cut carries its
    variant name. With no primary (nothing published), every cut is suffixed.
    `name` is `basics.name`; only the PDF uses it.
    """
    if fmt == "pdf":
        return pdf_filename(name, variant, primary_variant)
    if variant == primary_variant:
        return f"resume.{fmt}"
    return f"resume-{variant}.{fmt}"


def build_variant(
    resume: dict,
    variant: Variant,
    *,
    theme: str = "classic",
    primary_variant: str | None = None,
    formats: tuple[str, ...] = ("pdf", "html"),
    out_dir: Path = DIST_DIR,
) -> list[Artifact]:
    """Render one variant to the requested formats. Returns what was written."""
    data = apply_variant(resume, variant)
    # Stamped once per variant, not per format, so the artifacts of the same
    # cut can never disagree about what they are.
    stamp = build_stamp()
    label = variant.name if variant.name != primary_variant else None
    html = render_html(
        data, theme=theme, variant=label, stamp=stamp, style=variant.style
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    def target(fmt: str) -> Path:
        return out_dir / artifact_filename(
            fmt, data.get("basics", {}).get("name", ""), variant.name, primary_variant
        )

    written: list[Artifact] = []

    if "html" in formats:
        path = target("html")
        path.write_text(html, encoding="utf-8")
        written.append(Artifact(variant.name, "html", path))

    if "pdf" in formats:
        path = target("pdf")
        footer = render_print_footer(
            data, theme=theme, variant=label, stamp=stamp, style=variant.style
        )
        html_to_pdf(html, path, footer, metadata=document_metadata(data))
        written.append(Artifact(variant.name, "pdf", path))

    if "json" in formats:
        # The machine-readable cut: exactly what the theme rendered — variant
        # filtering applied, x-tags/x-highlights stripped — so a consumer of
        # this file can never see content the matching PDF does not show. The
        # stamp lands in `meta` (schema-blessed fields), carrying the same
        # provenance the human formats print in the colophon.
        payload = data
        if stamp:
            meta = {
                **(data.get("meta") or {}),
                "version": stamp.version,
                "lastModified": stamp.modified,
            }
            payload = {**data, "meta": meta}
        path = target("json")
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written.append(Artifact(variant.name, "json", path))

    if "md" in formats:
        md = render_markdown(data, theme=theme, variant=label, stamp=stamp)
        path = target("md")
        path.write_text(md, encoding="utf-8")
        written.append(Artifact(variant.name, "md", path))

    return written
