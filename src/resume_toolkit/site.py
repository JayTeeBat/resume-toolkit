"""The publishable site: every variant, plus an index page linking to them.

A workflow artifact is a bad front door — it needs a GitHub login, it is buried
several clicks inside an Actions run, and it expires. This module builds a
directory that GitHub Pages can serve at a stable public URL instead.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from .build import Artifact, build_variant
from .paths import DIST_DIR, REPO_ROOT, SITE_DIR
from .render import location, urlhost
from .variants import Variant, load_variants
from .version import build_stamp

INDEX_TEMPLATE = "index.html.j2"
LLMS_TEMPLATE = "llms.txt.j2"
NOT_FOUND_TEMPLATE = "404.html.j2"


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
        "md": f"resume-{variant.name}.md",
        "size": _human_size(pdf.stat().st_size),
    }


def _json_ld(resume: dict) -> Markup:
    """schema.org/Person markup for the index page, pre-serialized.

    Serialized here rather than in the template because autoescape would
    mangle the quotes; safe to inline because '<' is escaped, so the payload
    can never close its own <script> tag early. Search engines read this —
    it is the machine-readable that decides whether the page is *found*.
    """
    b = resume.get("basics") or {}
    loc = b.get("location") or {}
    address = {
        "@type": "PostalAddress",
        "addressLocality": loc.get("city"),
        "addressRegion": loc.get("region"),
        "addressCountry": loc.get("countryCode"),
    }
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": b.get("name"),
        "jobTitle": b.get("label"),
        "email": f"mailto:{b['email']}" if b.get("email") else None,
        "address": {k: v for k, v in address.items() if v} if any(loc.values()) else None,
        "url": (resume.get("meta") or {}).get("canonical"),
        "sameAs": [p["url"] for p in b.get("profiles") or [] if p.get("url")] or None,
    }
    payload = json.dumps({k: v for k, v in person.items() if v}, ensure_ascii=False)
    return Markup(payload.replace("<", "\\u003c"))


def _site_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(SITE_DIR),
        # llms.txt is plain text: autoescaping it would ship '&amp;' to agents.
        autoescape=lambda name: bool(name) and name.endswith(".html.j2"),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["location"] = location
    env.filters["urlhost"] = urlhost
    return env


def _render_index(resume: dict, cards: list[dict]) -> str:
    return _site_env().get_template(INDEX_TEMPLATE).render(
        resume=resume,
        cards=cards,
        source_url=_source_url(),
        json_ld=_json_ld(resume),
        generated=date.today().isoformat(),
    )


def _render_llms(resume: dict, cards: list[dict]) -> str:
    return _site_env().get_template(LLMS_TEMPLATE).render(resume=resume, cards=cards)


def _robots(canonical: str | None) -> str:
    """robots.txt: everything is meant to be found, so allow all and point at
    the sitemap (which needs absolute URLs, hence only when canonical is set)."""
    lines = ["User-agent: *", "Allow: /"]
    if canonical:
        lines += ["", f"Sitemap: {canonical.rstrip('/')}/sitemap.xml"]
    return "\n".join(lines) + "\n"


def _sitemap(canonical: str, cards: list[dict], modified: str | None) -> str:
    """The index plus every published variant's HTML — the pages worth crawling.

    PDFs, JSON and Markdown are downloads, not pages; the index links them and
    crawlers follow. lastmod comes from the content's git date, so it tells the
    truth the way the colophon does.
    """
    base = canonical.rstrip("/") + "/"
    lastmod = f"<lastmod>{modified}</lastmod>" if modified else ""
    urls = [base] + [base + c["html"] for c in cards]
    entries = "\n".join(f"  <url><loc>{u}</loc>{lastmod}</url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


def build_site(
    resume: dict,
    *,
    theme: str = "classic",
    out_dir: Path = DIST_DIR,
) -> list[Artifact]:
    """Build every publishable variant as PDF/HTML/JSON/Markdown, plus the front matter.

    The JSON and Markdown are machine- and paste-ready cuts of the same variant,
    so no consumer can ever disagree with the PDF about what the CV says. Only
    variants marked `publish = true` in variants.toml reach the page, so a CV
    tailored to one employer never leaks onto a public URL. Card order follows
    variants.toml, so reordering the file reorders the page.

    Beyond the variants, the site gets its front matter: index.html (the human
    front door), /resume.json (the guessable machine address — an alias of the
    primary cut), /llms.txt (the note an AI agent reads first), 404.html (the
    route back for dead links), and robots.txt + sitemap.xml (crawler guidance).
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
                resume, variant, theme=theme, formats=("pdf", "html", "json", "md"), out_dir=out_dir
            )
        )

    # The canonical machine address. `resume.json` is the filename the JSON
    # Resume ecosystem expects, and it hides the internal variant name from
    # the URL — the address survives renaming the variant behind it. Byte-for-
    # byte the primary (first published) cut, copied so the two cannot drift.
    primary = variants[0]
    alias = out_dir / "resume.json"
    alias.write_bytes((out_dir / f"resume-{primary.name}.json").read_bytes())
    written.append(Artifact(primary.name, "json", alias))

    # Cards are built after the PDFs exist, because each one reports its size.
    cards = [_card(v, out_dir) for v in variants]
    index = out_dir / "index.html"
    index.write_text(_render_index(resume, cards), encoding="utf-8")
    written.append(Artifact("index", "html", index))

    llms = out_dir / "llms.txt"
    llms.write_text(_render_llms(resume, cards), encoding="utf-8")
    written.append(Artifact("llms", "txt", llms))

    # Pages serves 404.html for any missing path — e.g. a bookmarked artifact
    # of a since-renamed variant. Its one job is routing back to the index.
    not_found = out_dir / "404.html"
    not_found.write_text(
        _site_env().get_template(NOT_FOUND_TEMPLATE).render(resume=resume), encoding="utf-8"
    )
    written.append(Artifact("404", "html", not_found))

    canonical = (resume.get("meta") or {}).get("canonical")
    robots = out_dir / "robots.txt"
    robots.write_text(_robots(canonical), encoding="utf-8")
    written.append(Artifact("robots", "txt", robots))

    if canonical:
        stamp = build_stamp()
        sitemap = out_dir / "sitemap.xml"
        sitemap.write_text(
            _sitemap(canonical, cards, stamp.modified if stamp else None), encoding="utf-8"
        )
        written.append(Artifact("sitemap", "xml", sitemap))

    return written
