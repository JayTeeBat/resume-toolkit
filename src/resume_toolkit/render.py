"""Jinja2 rendering of resume data into HTML."""

from __future__ import annotations

import base64
import re
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from .paths import THEMES_DIR
from .version import Stamp

MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


class UnknownTheme(Exception):
    pass


def theme_dir(theme: str) -> Path:
    path = THEMES_DIR / theme
    if not (path / "template.html.j2").is_file():
        known = sorted(p.name for p in THEMES_DIR.iterdir() if p.is_dir()) if THEMES_DIR.is_dir() else []
        raise UnknownTheme(f"unknown theme {theme!r}; themes/ holds: {', '.join(known) or '(none)'}")
    return path


def pdate(value: str | None) -> str:
    """Format a JSON Resume iso8601 date for display.

    The schema allows YYYY, YYYY-MM or YYYY-MM-DD, so all three must survive.
    """
    if not value:
        return ""
    parts = str(value).split("-")
    year = parts[0]
    if len(parts) == 1:
        return year
    try:
        return f"{MONTHS[int(parts[1]) - 1]} {year}"
    except (ValueError, IndexError):
        return year


def daterange(entry: dict) -> str:
    """`startDate`–`endDate` for an entry; a missing endDate means ongoing."""
    start = pdate(entry.get("startDate"))
    end = pdate(entry.get("endDate"))
    if not start and not end:
        return ""
    if not start:
        return end
    return f"{start} – {end or 'Present'}"


def location(loc: dict | None) -> str:
    """`City, Region, CC` from a basics.location object, skipping blanks."""
    if not loc:
        return ""
    parts = [loc.get("city"), loc.get("region"), loc.get("countryCode")]
    return ", ".join(p for p in parts if p)


def urlhost(url: str | None) -> str:
    """Strip scheme and trailing slash — `https://x.dev/` reads better as `x.dev`."""
    if not url:
        return ""
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def _environment(theme_path: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(theme_path),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        # Default Undefined, deliberately: most schema sections are optional, so
        # `{% if resume.awards %}` on an absent key must be falsy, not an error.
    )
    env.filters["pdate"] = pdate
    env.filters["daterange"] = daterange
    env.filters["location"] = location
    env.filters["urlhost"] = urlhost
    return env


def _inline_stylesheet(theme_path: Path) -> Markup:
    """Read style.css and embed its fonts as data URIs, returning a <style> tag.

    Inlining serves both outputs: the HTML export becomes a single portable
    file, and the PDF renderer never races a separate font request.
    """
    css = (theme_path / "style.css").read_text(encoding="utf-8")

    def embed(match: re.Match[str]) -> str:
        rel = match.group("path")
        font = theme_path / rel
        if not font.is_file():
            raise FileNotFoundError(f"{theme_path.name}/style.css references missing font: {rel}")
        payload = base64.b64encode(font.read_bytes()).decode("ascii")
        return f"url('data:font/woff2;base64,{payload}') format('woff2')"

    css = re.sub(
        r"url\(\s*['\"](?P<path>[^'\"]+\.woff2)['\"]\s*\)\s*format\(\s*['\"]woff2['\"]\s*\)",
        embed,
        css,
    )
    # Markup, not str: autoescape is on, and CSS must reach the page as markup.
    return Markup(f"<style>\n{css}\n</style>")


def render_html(
    resume: dict,
    theme: str = "classic",
    *,
    variant: str | None = None,
    stamp: Stamp | None = None,
) -> str:
    """Render resume data to a single self-contained HTML document.

    `variant` and `stamp` are passed in rather than looked up here: this module
    stays a pure function of its arguments, and the git calls behind a stamp
    belong with the rest of the orchestration in build.py. Both are optional, so
    a theme still renders without provenance.
    """
    path = theme_dir(theme)
    env = _environment(path)
    template = env.get_template("template.html.j2")
    return template.render(
        resume=resume,
        stylesheet=_inline_stylesheet(path),
        generated=date.today().isoformat(),
        variant=variant,
        stamp=stamp,
    )
