"""The publishable site: every variant, plus an index page linking to them.

A workflow artifact is a bad front door — it needs a GitHub login, it is buried
several clicks inside an Actions run, and it expires. This module builds a
directory that GitHub Pages can serve at a stable public URL instead.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .build import Artifact, build_variant
from .paths import DIST_DIR, REPO_ROOT, SITE_DIR
from .render import location
from .variants import Variant, load_variants

INDEX_TEMPLATE = "index.html.j2"


def _human_size(num_bytes: int) -> str:
    return f"{num_bytes / 1024:.0f} KB"


def _source_url() -> str | None:
    """Best-effort link back to resume.json on GitHub, or None if not derivable.

    Actions sets GITHUB_REPOSITORY, so CI needs no guessing. Locally we read the
    origin remote, which also copes with SSH host aliases like
    `github-perso:owner/repo.git`.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        try:
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
        match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", remote)
        if not match:
            return None
        repo = match.group(1)
    return f"https://github.com/{repo}/blob/main/resume.json"


def _card(variant: Variant, out_dir: Path) -> dict:
    pdf = out_dir / f"resume-{variant.name}.pdf"
    return {
        "name": variant.name,
        "description": variant.description,
        "pdf": pdf.name,
        "html": f"resume-{variant.name}.html",
        "json": f"resume-{variant.name}.json",
        "size": _human_size(pdf.stat().st_size),
    }


def _render_index(resume: dict, cards: list[dict]) -> str:
    env = Environment(
        loader=FileSystemLoader(SITE_DIR),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["location"] = location
    return env.get_template(INDEX_TEMPLATE).render(
        resume=resume,
        cards=cards,
        source_url=_source_url(),
        generated=date.today().isoformat(),
    )


def build_site(
    resume: dict,
    *,
    theme: str = "classic",
    out_dir: Path = DIST_DIR,
) -> list[Artifact]:
    """Build every publishable variant as PDF + HTML + JSON, then an index linking them.

    The JSON is the machine-readable cut of the same variant, so a parser and a
    reader can never disagree about what the CV says. Only variants marked
    `publish = true` in variants.toml reach the page, so a CV tailored to one
    employer never leaks onto a public URL. Card order follows variants.toml,
    so reordering the file reorders the page.
    """
    variants = [v for v in load_variants().values() if v.publish]
    if not variants:
        raise ValueError(
            "no publishable variants: mark at least one with `publish = true` in variants.toml"
        )

    written: list[Artifact] = []
    for variant in variants:
        written.extend(
            build_variant(
                resume, variant, theme=theme, formats=("pdf", "html", "json"), out_dir=out_dir
            )
        )

    # Cards are built after the PDFs exist, because each one reports its size.
    cards = [_card(v, out_dir) for v in variants]
    index = out_dir / "index.html"
    index.write_text(_render_index(resume, cards), encoding="utf-8")
    written.append(Artifact("index", "html", index))

    return written
