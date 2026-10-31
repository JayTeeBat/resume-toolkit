"""Filesystem and Chromium boundaries for quality checks."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

from ..build import build_variant
from ..pdf import chromium, open_page, print_page
from ..render import render_print_footer
from ..variants import Variant, apply_variant
from ..version import build_stamp
from .common import Violation, finish
from .config import CheckConfig, checked_variants, page_budget_for


def codespell(root: Path, config: CheckConfig) -> list[Violation]:
    # Generated output and environments are never prose inputs. Keep project
    # codespell settings for all remaining source files.
    inputs = [
        f"./{path.name}"
        for path in sorted(root.iterdir())
        if path.name not in {"dist", ".git", ".venv"}
    ]
    if not inputs:
        return []
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "codespell_lib",
            "--ignore-words-list",
            ",".join(config.codespell_ignore_words),
            *inputs,
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
    violations = []
    for target in checked_variants("page_budget", config, variants):
        budget = page_budget_for(config, target.name)
        if budget is None:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            written = build_variant(resume, target, formats=("pdf",), out_dir=Path(tmp))
            pages = len(PdfReader(written[0].path).pages)
        if pages > budget:
            violations.append(
                Violation(
                    f"variant {target.name}",
                    f"{pages} pages; budget {budget}",
                    "trim or tag entries out of the cut (x-tags), or tighten the "
                    "theme's spacing tokens (--size-base, --leading, --section-gap)",
                )
            )
    return finish("page_budget", violations)


def header(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    violations = []
    with tempfile.TemporaryDirectory() as tmp, chromium() as browser:
        for target in checked_variants("header", config, variants):
            written = build_variant(
                resume, target, formats=("html",), out_dir=Path(tmp)
            )
            for media in ("screen", "print"):
                width = (
                    config.print_content_width
                    if media == "print"
                    else config.screen_width
                )
                page = open_page(browser, written[0].path, width)
                page.emulate_media(media=media)
                items = page.locator(".contact li").evaluate_all(
                    "items => items.map(item => ({text: item.innerText, "
                    "top: item.getBoundingClientRect().top}))"
                )
                if len({item["top"] for item in items}) > 1:
                    violations.append(
                        Violation(
                            f"variant {target.name}: .contact li ({media}): "
                            + "; ".join(item["text"] for item in items),
                            "top offsets: "
                            + ", ".join(str(item["top"]) for item in items),
                            "shorten or drop one contact item so every "
                            "item shares the same top offset",
                        )
                    )
                page.close()
    return finish("header", violations)


#: Pins two 1px link annotations inside every company and role block: one at
#: its top edge and one at its bottom edge. Absolutely positioned, so layout is
#: untouched, and prepended, so :last-child styling is too. Chromium writes
#: each into the PDF on the page where that edge was laid out.
_MARK_EDGES = """blocks => blocks.forEach((block, i) => {
  if (getComputedStyle(block).position === 'static') block.style.position = 'relative';
  for (const edge of ['bottom', 'top']) {
    const mark = document.createElement('a');
    mark.href = 'MARK_PREFIX' + i + '/' + edge;
    mark.style.cssText = `position:absolute;${edge}:0;left:0;width:1px;height:1px`;
    block.prepend(mark);
  }
})"""
_MARK = "https://page-breaks.invalid/"
_BLOCKS = ".company, .role"


def _edge_pages(pdf: Path) -> dict[tuple[int, str], int]:
    """(block index, 'top'|'bottom') -> 1-based page that edge printed on."""
    edges = {}
    for number, pdf_page in enumerate(PdfReader(pdf).pages, start=1):
        for annot in pdf_page.get("/Annots") or []:
            uri = str(annot.get_object().get("/A", {}).get("/URI", ""))
            if uri.startswith(_MARK):
                index, edge = uri.removeprefix(_MARK).split("/")
                edges.setdefault((int(index), edge), number)
    return edges


def page_breaks(
    resume: dict, config: CheckConfig, variants: dict[str, Variant]
) -> list[Violation]:
    """No page break inside a role, nor inside a company that fits one page.

    Pagination is read back from the printed PDF itself rather than predicted:
    the cut is printed through the same code path as `resume build`, with
    invisible marks at each block's top and bottom edges. A block whose edges
    land on different pages was split. Unfragmented block heights come from
    the same HTML laid out for print at print_content_width, and are compared
    with print_content_height to tell an avoidable company split from one that
    is taller than a page and may break between its roles.
    """
    violations = []
    with tempfile.TemporaryDirectory() as tmp, chromium() as browser:
        for target in checked_variants("page_breaks", config, variants):
            out = Path(tmp) / target.name
            html = build_variant(resume, target, formats=("html",), out_dir=out)[0].path
            data = apply_variant(resume, target)
            footer = render_print_footer(
                data, variant=target.name, stamp=build_stamp(), style=target.style
            )

            measure = open_page(browser, html, config.print_content_width)
            measure.emulate_media(media="print")
            blocks = measure.locator(_BLOCKS).evaluate_all(
                "blocks => blocks.map(b => ({"
                "role: b.classList.contains('role'), "
                "name: (b.querySelector('.company-name, .role-title') || b)"
                ".innerText.trim(), "
                "height: Math.round(b.getBoundingClientRect().height)}))"
            )
            measure.close()

            printed = open_page(browser, html)
            printed.locator(_BLOCKS).evaluate_all(
                _MARK_EDGES.replace("MARK_PREFIX", _MARK)
            )
            edges = _edge_pages(print_page(printed, out / "probe.pdf", footer))
            printed.close()

            company = ""
            for i, block in enumerate(blocks):
                if not block["role"]:
                    company = block["name"]
                first, last = edges.get((i, "top")), edges.get((i, "bottom"))
                if first is None or last is None or first == last:
                    continue
                if block["role"]:
                    violations.append(
                        Violation(
                            f"variant {target.name}: {company} — {block['name']}",
                            f"role breaks across pages {first}–{last}",
                            "tag bullets out of this cut (x-highlights) or trim "
                            "the role until it fits on one page; the theme must "
                            "keep .role `break-inside: avoid`",
                        )
                    )
                elif block["height"] <= config.print_content_height:
                    violations.append(
                        Violation(
                            f"variant {target.name}: {company}",
                            f"pages {first}–{last}; {block['height']} px tall, "
                            f"a page holds {config.print_content_height} px",
                            "keep .company `break-inside: avoid` in the theme, or "
                            "trim content around the break so the company starts "
                            "on a fresh page",
                        )
                    )
    return finish("page_breaks", violations)
