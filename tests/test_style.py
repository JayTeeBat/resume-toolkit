"""Variant design tokens are validated and shared by exports and checks."""

import itertools
from dataclasses import replace
from pathlib import Path

import pytest
from pypdf import PdfReader
from typer.testing import CliRunner

from resume_toolkit.build import build_variant
from resume_toolkit.checks import external
from resume_toolkit.checks.config import CheckConfig
from resume_toolkit.cli import app
from resume_toolkit.pdf import chromium, open_page
from resume_toolkit.render import render_html, render_print_footer
from resume_toolkit.variants import Variant, load_variants


@pytest.mark.parametrize(
    "body",
    [
        'density = "compact"',
        "description = 3",
        'include = "full"',
        "include = [1]",
        'publish = "yes"',
        'style = "compact"',
        'style = { color = "red" }',
        'style = { "--size-base" = 9 }',
        'style = { "--size-base" = "" }',
        *[f'style = {{ "--size-base" = "9pt{c}" }}' for c in ";{}<"],
        'style = { "--size-base" = "9pt/*" }',
        'style = { "--size-base" = "9pt\\\\" }',
    ],
)
def test_invalid_variant_configuration(tmp_path, body) -> None:
    path = tmp_path / "variants.toml"
    path.write_text("[short]\n" + body + "\n")
    with pytest.raises(ValueError, match="variant short"):
        load_variants(path)


def test_style_loads_and_defaults_are_isolated(tmp_path) -> None:
    path = tmp_path / "variants.toml"
    path.write_text('[compact]\nstyle = { "--size-base" = "9pt" }\n[full]\n')
    cuts = load_variants(path)
    assert cuts["compact"].style == {"--size-base": "9pt"}
    assert cuts["full"].style == {}


def test_unknown_theme_token_is_an_error(resume) -> None:
    with pytest.raises(ValueError, match="unknown theme tokens: --typo"):
        render_html(resume, style={"--typo": "9pt"})


def test_overrides_follow_theme_and_do_not_leak(resume) -> None:
    original = render_html(resume, variant="full")
    style = {"--size-base": "9pt", "--size-footer": "7.5pt"}
    compact = render_html(resume, variant="compact", style=style)
    assert compact.index("--size-base: 9pt") > compact.index("@media print")
    footer = render_print_footer(resume, style=style)
    assert footer is not None
    assert "--size-footer: 7.5pt" in footer
    assert render_html(resume, variant="full") == original
    assert render_html(resume, variant="full", style={}) == original


def test_invalid_style_cli_error_contract(tmp_path, monkeypatch, resume) -> None:
    import json

    monkeypatch.chdir(tmp_path)
    Path("resume.json").write_text(json.dumps(resume))
    Path("variants.toml").write_text('[short]\nstyle = { color = "red" }\n')
    monkeypatch.setattr("resume_toolkit.site.load_variants", load_variants)
    runner = CliRunner()
    for args in [["variants"], ["build"], ["site"], ["serve"]]:
        result = runner.invoke(app, args)
        assert result.exit_code == 2
        assert "error: variant short.style" in result.output
    result = runner.invoke(app, ["check", "--fast", "--format", "json"])
    assert result.exit_code == 2
    assert "CSS custom property" in json.loads(result.output)["error"]


@pytest.mark.slow
def test_html_pdf_and_checks_use_variant_style(resume, tmp_path, monkeypatch) -> None:
    normal = Variant("normal", "", frozenset(), publish=True)
    compact = replace(
        normal, name="compact", style={"--size-base": "9pt", "--leading": "1.2"}
    )
    for cut, expected in [(normal, 12.8), (compact, 12.0)]:
        artifacts = build_variant(resume, cut, out_dir=tmp_path)
        with chromium() as browser:
            page = open_page(
                browser, next(a.path for a in artifacts if a.fmt == "html")
            )
            assert float(
                page.evaluate("parseFloat(getComputedStyle(document.body).fontSize)")
            ) == pytest.approx(expected)
        sizes = []
        pdf = PdfReader(next(a.path for a in artifacts if a.fmt == "pdf"))
        pdf.pages[0].extract_text(
            visitor_text=lambda text, cm, tm, font, size, sizes=sizes: (
                sizes.append(size) if "Build reliable" in text else None
            )
        )
        assert sizes == [pytest.approx(expected)]

    observed = []
    original = external.open_page

    def measured(browser, path, width=None):
        page = original(browser, path, width)
        observed.append(page.evaluate("getComputedStyle(document.body).fontSize"))
        return page

    monkeypatch.setattr(external, "open_page", measured)
    config = CheckConfig()
    cuts = {"compact": compact}
    assert external.header(resume, config, cuts) == []
    assert external.page_breaks(resume, config, cuts) == []
    assert observed == ["12px"] * 4
    # A tall role exceeds one page at default spacing but fits with an override.
    resume["work"][0]["highlights"] *= 38
    assert external.page_budget(
        resume, replace(config, page_budget=1), {"normal": normal}
    )
    assert external.page_budget(resume, replace(config, page_budget=1), cuts) == []


@pytest.mark.slow
@pytest.mark.parametrize("dirty", [False, True])
def test_footer_geometry_is_identical_across_body_styles(
    resume, tmp_path, dirty
) -> None:
    """Body tokens never reach the footer: every cut gets one 7.5pt line whose
    four fields sit at equal gaps from margin to margin, a separator centred
    in each gap."""
    from resume_toolkit.version import Stamp

    stamp = Stamp(
        "2026.01.01+1234567" + (".dirty" if dirty else ""),
        "2026-01-01",
        dirty,
        "2026-01-01 · rev 1234567" + (" (modified)" if dirty else ""),
    )
    resume["meta"]["canonical"] = "https://ada.example.org/curriculum-vitae"
    geometries = []
    with chromium() as browser:
        for variant in ["one-page", "2-page", "full"]:
            footer = render_print_footer(
                resume,
                variant=variant,
                stamp=stamp,
                style={"--size-base": "9pt", "--leading": "1.2"}
                if variant == "one-page"
                else None,
            )
            assert footer is not None
            path = tmp_path / f"{variant}.html"
            path.write_text(footer)
            page = open_page(browser, path, 794)
            page.emulate_media(media="print")
            zones = page.locator(".running-footer > .field").evaluate_all(
                """els => els.map(e => {
                    const r = e.getBoundingClientRect();
                    const s = getComputedStyle(e);
                    return {left: r.left, right: r.right, top: r.top,
                            height: r.height, size: s.fontSize,
                            leading: s.lineHeight, wrap: s.whiteSpace};
                })"""
            )
            assert len(zones) == 4
            seps = page.locator(".running-footer > .sep").evaluate_all(
                "els => els.map(e => e.getBoundingClientRect())"
                ".map(r => (r.left + r.right) / 2)"
            )
            for sep, (a, b) in zip(seps, itertools.pairwise(zones), strict=True):
                assert sep == pytest.approx((a["right"] + b["left"]) / 2, abs=0.5)
            gaps = [b["left"] - a["right"] for a, b in itertools.pairwise(zones)]
            assert min(gaps) > 0
            assert max(gaps) - min(gaps) == pytest.approx(0, abs=0.02)
            # A4 at 96 dpi is 794 px wide; 14 mm side padding is ~52.9 px.
            assert zones[0]["left"] == pytest.approx(52.9, abs=0.1)
            assert zones[-1]["right"] == pytest.approx(794 - 52.9, abs=0.1)
            assert {z["size"] for z in zones} == {"10px"}
            assert {z["leading"] for z in zones} == {"13.5px"}
            assert {z["wrap"] for z in zones} == {"nowrap"}
            assert len({z["top"] for z in zones}) == 1
            geometries.append(zones[-1])
            page.close()
    assert geometries[0] == geometries[1] == geometries[2]
