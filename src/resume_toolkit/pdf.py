"""Chromium print-to-PDF via Playwright."""

from __future__ import annotations

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


class BrowserMissing(Exception):
    """Playwright is installed but its Chromium build is not."""


def html_to_pdf(html: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)

    # Write the HTML to a real file and navigate to it, rather than using
    # set_content(): a file:// origin gives relative asset paths a base URL to
    # resolve against. (Assets are inlined today, but this keeps a theme that
    # references an image from silently rendering blank.)
    with tempfile.TemporaryDirectory() as tmp:
        page_file = Path(tmp) / "resume.html"
        page_file.write_text(html, encoding="utf-8")

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:  # noqa: BLE001 - re-raised with a fix hint
                raise BrowserMissing(
                    f"could not launch Chromium ({exc}).\n"
                    "Run:  uv run playwright install chromium"
                ) from exc

            try:
                page = browser.new_page()
                page.goto(page_file.as_uri(), wait_until="load")
                # Ensure webfonts are decoded before layout is measured,
                # otherwise pagination can be computed against fallback metrics.
                page.evaluate("() => document.fonts.ready")
                # Apply @media print rules; without this the screen styles win.
                page.emulate_media(media="print")
                page.pdf(
                    path=str(out),
                    print_background=True,
                    # Let the stylesheet's @page rule own size and margins,
                    # instead of Chromium's ~1cm defaults.
                    prefer_css_page_size=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                browser.close()

    return out
