"""Filesystem and Chromium boundaries for quality checks."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from ..build import build_variant
from ..pdf import BrowserMissing
from ..variants import Variant
from .common import Violation, finish
from .config import CheckConfig, published_variant


def codespell(root: Path, config: CheckConfig) -> list[Violation]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "codespell_lib",
            "--ignore-words-list",
            ",".join(config.codespell_ignore_words),
            ".",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    violations = []
    for line in result.stdout.splitlines():
        match = re.match(r"(.+?:\d+): (.+?) ==> (.+)", line)
        if match:
            where, text, replacement = match.groups()
            violations.append(
                Violation(
                    where,
                    text,
                    f"write {replacement}, or add a proper noun to "
                    f"codespell_ignore_words",
                )
            )
    if not violations:
        violations.append(
            Violation(
                str(root),
                result.stderr.strip() or result.stdout.strip(),
                "run `uv sync` and correct the codespell configuration",
            )
        )
    return finish("codespell", violations)


def page_budget(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    target = published_variant(config, variants)
    with tempfile.TemporaryDirectory() as tmp:
        written = build_variant(resume, target, formats=("pdf",), out_dir=Path(tmp))
        pages = len(PdfReader(written[0].path).pages)
    return finish(
        "page_budget",
        [
            Violation(
                f"variant {target.name}",
                f"{pages} pages; budget {config.page_budget}",
                "trim or tag entries out of the cut (x-tags), or tighten the "
                "theme's spacing tokens (--size-base, --leading, --section-gap)",
            )
        ]
        if pages > config.page_budget
        else [],
    )


def header(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = []
    with tempfile.TemporaryDirectory() as tmp:
        written = build_variant(
            resume,
            published_variant(config, variants),
            formats=("html",),
            out_dir=Path(tmp),
        )
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:  # noqa: BLE001 - actionable infrastructure error
                raise BrowserMissing(
                    "could not launch Chromium; run `uv run playwright "
                    "install chromium`"
                ) from exc
            try:
                for media in ("screen", "print"):
                    width = (
                        config.print_content_width
                        if media == "print"
                        else config.screen_width
                    )
                    page = browser.new_page(viewport={"width": width, "height": 1123})
                    page.emulate_media(media=media)
                    page.goto(written[0].path.as_uri(), wait_until="load")
                    page.evaluate("() => document.fonts.ready")
                    items = page.locator(".contact li").evaluate_all(
                        "items => items.map(item => ({text: item.innerText, "
                        "top: item.getBoundingClientRect().top}))"
                    )
                    if len({item["top"] for item in items}) > 1:
                        violations.append(
                            Violation(
                                f".contact li ({media}): "
                                + "; ".join(item["text"] for item in items),
                                "top offsets: "
                                + ", ".join(str(item["top"]) for item in items),
                                "shorten or drop one contact item so every "
                                "item shares the same top offset",
                            )
                        )
                    page.close()
            finally:
                browser.close()
    return finish("header", violations)
