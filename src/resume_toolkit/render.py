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


def group_work(entries: list[dict] | None) -> list[dict]:
    """Group adjacent roles at the same employer for human-facing output.

    The JSON Resume source keeps one standard ``work`` entry per role.  This
    view layer adds company tenure and shared location without changing that
    portable source shape.  Only adjacent entries are grouped: returning to a
    former employer later in a career remains a separate chronology event.
    """
    groups: list[dict] = []
    for job in entries or []:
        name = job.get("name")
        if name and groups and groups[-1]["name"] == name:
            groups[-1]["roles"].append(job)
        else:
            groups.append({"name": name, "url": job.get("url"), "roles": [job]})

    for group in groups:
        roles = group["roles"]
        starts = [role["startDate"] for role in roles if role.get("startDate")]
        ends = [role["endDate"] for role in roles if role.get("endDate")]
        if starts:
            group["startDate"] = min(starts)
        if len(ends) == len(roles) and ends:
            group["endDate"] = max(ends)

        locations = {role.get("location") for role in roles if role.get("location")}
        if len(locations) == 1:
            group["location"] = locations.pop()

    return groups


def _environment(theme_path: Path, *, autoescape: bool = True) -> Environment:
    env = Environment(
        loader=FileSystemLoader(theme_path),
        autoescape=autoescape,
        trim_blocks=True,
        lstrip_blocks=True,
        # Default Undefined, deliberately: most schema sections are optional, so
        # `{% if resume.awards %}` on an absent key must be falsy, not an error.
    )
    env.filters["pdate"] = pdate
    env.filters["daterange"] = daterange
    env.filters["location"] = location
    env.filters["urlhost"] = urlhost
    env.filters["group_work"] = group_work
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


def render_markdown(
    resume: dict,
    theme: str = "classic",
    *,
    variant: str | None = None,
    stamp: Stamp | None = None,
) -> str:
    """Render resume data to a paste-ready Markdown document.

    The format exists for the places styled output cannot go: ATS web forms,
    plain-text emails, LLM contexts. It follows the theme's template.md.j2 so
    section order stays the theme's editorial call, like the HTML. Autoescape
    is off — Markdown is plain text, and '&' must stay '&'.
    """
    env = _environment(theme_dir(theme), autoescape=False)
    return env.get_template("template.md.j2").render(
        resume=resume,
        generated=date.today().isoformat(),
        variant=variant,
        stamp=stamp,
    )
