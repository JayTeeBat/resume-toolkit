"""Chromium print-to-PDF via Playwright."""

from __future__ import annotations

import re
import tempfile
import unicodedata
from collections.abc import Generator
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright
from pypdf import PdfWriter


def pdf_filename(name: str, variant: str, primary_variant: str | None = None) -> str:
    """A portable, self-identifying filename; only the primary cut omits its name."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9-]", "", "-".join(folded.split()))
    if not slug:
        raise ValueError("basics.name must produce a nonempty ASCII PDF filename")
    suffix = (
        ""
        if variant == primary_variant
        else "-" + "-".join(part.title() for part in variant.split("-"))
    )
    return f"{slug}-Resume{suffix}.pdf"


def document_metadata(resume: dict) -> dict[str, str]:
    """Metadata from the rendered cut, never from unfiltered source content."""
    basics = resume.get("basics") or {}
    keywords = dict.fromkeys(
        keyword
        for skill in resume.get("skills") or []
        for keyword in skill.get("keywords") or []
    )
    return {
        "/Author": basics.get("name", ""),
        "/Subject": basics.get("label", ""),
        "/Keywords": ", ".join(keywords),
    }


def write_metadata(path: Path, metadata: dict[str, str]) -> None:
    """Keep Chromium's title, dates and page content; add no generated IDs."""
    writer = PdfWriter(clone_from=BytesIO(path.read_bytes()))
    writer.add_metadata(metadata)
    writer.write(path)


class BrowserMissing(Exception):
    """Playwright is installed but its Chromium build is not."""


@contextmanager
def chromium() -> Generator[Browser]:
    """A launched Chromium, or BrowserMissing with the command that fixes it."""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - re-raised with a fix hint
            raise BrowserMissing(
                f"could not launch Chromium ({exc}).\n"
                "Run:  uv run playwright install chromium"
            ) from exc
        try:
            yield browser
        finally:
            browser.close()


def open_page(browser: Browser, path: Path, width: int | None = None) -> Page:
    """Load a rendered HTML file with its webfonts decoded.

    `width` sets the viewport for layout measurements; printing ignores it.
    """
    page = (
        browser.new_page(viewport={"width": width, "height": 1123})
        if width
        else browser.new_page()
    )
    page.goto(path.as_uri(), wait_until="load")
    # Ensure webfonts are decoded before layout is measured,
    # otherwise pagination can be computed against fallback metrics.
    page.evaluate("() => document.fonts.ready")
    return page


def print_page(page: Page, out: Path, footer: str | None = None) -> Path:
    """Print a loaded page to PDF; the one code path every PDF goes through.

    `footer` is a Chromium footer template (see render.render_print_footer). It
    is drawn inside the @page bottom margin on every page, so the content area,
    and with it the pagination, is the same with or without it.
    """
    # Apply @media print rules; without this the screen styles win.
    page.emulate_media(media="print")
    page.pdf(
        path=str(out),
        print_background=True,
        # Let the stylesheet's @page rule own size and margins,
        # instead of Chromium's ~1cm defaults.
        prefer_css_page_size=True,
        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        display_header_footer=footer is not None,
        # An empty header template: Chromium's default prints the date and title.
        header_template="<span></span>",
        footer_template=footer or "<span></span>",
    )
    return out


def html_to_pdf(
    html: str,
    out: Path,
    footer: str | None = None,
    *,
    metadata: dict[str, str] | None = None,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)

    # Write the HTML to a real file and navigate to it, rather than using
    # set_content(): a file:// origin gives relative asset paths a base URL to
    # resolve against. (Assets are inlined today, but this keeps a theme that
    # references an image from silently rendering blank.)
    with tempfile.TemporaryDirectory() as tmp:
        page_file = Path(tmp) / "resume.html"
        page_file.write_text(html, encoding="utf-8")
        with chromium() as browser:
            print_page(open_page(browser, page_file), out, footer)

    if metadata is not None:
        write_metadata(out, metadata)
    return out
