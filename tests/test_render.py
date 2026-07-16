"""HTML rendering and its date/location helpers."""

from __future__ import annotations

import pytest

from resume_toolkit.render import UnknownTheme, daterange, location, pdate, render_html, urlhost
from resume_toolkit.version import Stamp


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2014", "2014"),          # the schema allows a bare year
        ("2014-06", "Jun 2014"),
        ("2014-06-29", "Jun 2014"),
        ("", ""),
        (None, ""),
    ],
)
def test_pdate_handles_every_shape_the_schema_allows(value, expected) -> None:
    assert pdate(value) == expected


def test_daterange_marks_a_missing_end_as_ongoing() -> None:
    assert daterange({"startDate": "2022-01"}) == "Jan 2022 – Present"


def test_daterange_with_both_ends() -> None:
    assert daterange({"startDate": "2019-03", "endDate": "2021-12"}) == "Mar 2019 – Dec 2021"


def test_daterange_of_an_undated_entry_is_empty() -> None:
    assert daterange({"name": "Thing"}) == ""


def test_location_skips_blank_parts() -> None:
    assert location({"city": "Lyon", "countryCode": "FR"}) == "Lyon, FR"
    assert location({}) == ""
    assert location(None) == ""


def test_urlhost_strips_scheme_and_trailing_slash() -> None:
    assert urlhost("https://www.example.com/") == "example.com"
    assert urlhost(None) == ""


def test_render_omits_sections_absent_from_the_document() -> None:
    """Optional schema sections must be falsy, not an error."""
    html = render_html({"basics": {"name": "Ada Lovelace"}})

    assert "Ada Lovelace" in html
    assert "Experience" not in html
    assert "Awards" not in html


def test_colophon_identifies_the_cut_and_the_build() -> None:
    """The whole point of the footer: a stray PDF must say what it is."""
    html = render_html(
        {"basics": {"name": "Ada"}, "meta": {"canonical": "https://example.com/cv/"}},
        variant="acme",
        stamp=Stamp(version="2026.07.16+g942700c", modified="2026-07-16", dirty=False),
    )

    assert "acme cut" in html
    assert "2026.07.16+g942700c" in html
    assert 'href="https://example.com/cv/"' in html


def test_colophon_degrades_when_there_is_nothing_to_stamp() -> None:
    """No git and no canonical must not leave an empty bordered strip.

    Asserts on the markup, not the string "colophon": the class name also
    appears in the inlined stylesheet, so it is present either way.
    """
    html = render_html({"basics": {"name": "Ada"}})

    assert "<footer" not in html


def test_colophon_survives_a_resume_with_no_meta_block() -> None:
    """`meta` is optional in the schema; reaching through it must not raise."""
    html = render_html({"basics": {"name": "Ada"}}, variant="full")

    assert "full cut" in html
    assert "latest at" not in html


def test_render_inlines_fonts_and_styles() -> None:
    html = render_html({"basics": {"name": "Ada"}})

    assert "<style>" in html
    assert "url('data:font/woff2;base64," in html
    assert ".woff2') format" not in html, "a font escaped inlining"


def test_render_escapes_content() -> None:
    html = render_html({"basics": {"name": "<script>alert(1)</script>"}})

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_unknown_theme_names_the_known_ones() -> None:
    with pytest.raises(UnknownTheme, match="classic"):
        render_html({"basics": {"name": "Ada"}}, theme="no-such-theme")
