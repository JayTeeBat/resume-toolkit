"""HTML/Markdown rendering and its date/location helpers."""

from __future__ import annotations

import pytest

from resume_toolkit.render import (
    UnknownTheme,
    daterange,
    group_work,
    location,
    pdate,
    render_html,
    render_markdown,
    urlhost,
)
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


def test_group_work_combines_adjacent_roles_and_derives_company_tenure() -> None:
    work = [
        {
            "name": "Analytical Engines",
            "position": "Lead Engineer",
            "location": "London",
            "startDate": "1844-01",
        },
        {
            "name": "Analytical Engines",
            "position": "Engineer",
            "location": "London",
            "startDate": "1842-01",
            "endDate": "1843-12",
        },
        {
            "name": "Royal Society",
            "position": "Fellow",
            "startDate": "1841-01",
            "endDate": "1841-12",
        },
    ]

    grouped = group_work(work)

    assert [group["name"] for group in grouped] == ["Analytical Engines", "Royal Society"]
    assert [role["position"] for role in grouped[0]["roles"]] == ["Lead Engineer", "Engineer"]
    assert grouped[0]["startDate"] == "1842-01"
    assert "endDate" not in grouped[0], "one current role makes the company tenure current"
    assert grouped[0]["location"] == "London"


def test_group_work_does_not_merge_non_adjacent_returns_to_an_employer() -> None:
    grouped = group_work(
        [
            {"name": "A", "position": "Third"},
            {"name": "B", "position": "Second"},
            {"name": "A", "position": "First"},
        ]
    )

    assert [group["name"] for group in grouped] == ["A", "B", "A"]


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


def test_colophon_claims_resume_as_code_when_meta_names_a_source() -> None:
    """`meta.source` turns the footer into the resume-as-code claim + repo link."""
    html = render_html({"basics": {"name": "Ada"}, "meta": {"source": "https://github.com/ada/cv"}})

    assert "resume-as-code" in html
    assert 'href="https://github.com/ada/cv"' in html


def test_colophon_survives_a_resume_with_no_meta_block() -> None:
    """`meta` is optional in the schema; reaching through it must not raise."""
    html = render_html({"basics": {"name": "Ada"}}, variant="full")

    assert "full cut" in html
    assert "latest at" not in html


def test_html_head_carries_an_initials_favicon() -> None:
    """The HTML export is opened in browser tabs (the index links it), and a
    tab with the default globe icon is a tab you cannot find again."""
    html = render_html({"basics": {"name": "Ada King Lovelace"}})

    assert 'rel="icon"' in html
    # First two initials, embedded in the SVG data URI ("%3E" encodes ">").
    assert "%3EAK%3C" in html


def test_html_is_responsive_on_small_screens() -> None:
    html = render_html({"basics": {"name": "Ada Lovelace"}})

    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert "@media screen and (max-width: 640px)" in html
    assert "width: 100%" in html


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


def test_markdown_render_is_plain_text_not_escaped_html() -> None:
    """The whole point of the format is pasting it somewhere; '&amp;' in an
    ATS form field would be a visible bug."""
    md = render_markdown(
        {
            "basics": {"name": "Ada Lovelace", "label": "R&D Lead", "summary": "Did X."},
            "work": [
                {
                    "name": "Analytical Engines",
                    "position": "Engineer",
                    "startDate": "1842-01",
                    "highlights": ["Programmed the engine."],
                }
            ],
        }
    )

    assert md.startswith("# Ada Lovelace")
    assert "R&D Lead" in md
    assert "&amp;" not in md
    assert "### Engineer — Analytical Engines (Jan 1842 – Present)" in md
    assert "- Programmed the engine." in md


def test_render_uses_same_company_heading_for_grouped_and_single_roles() -> None:
    resume = {
        "basics": {"name": "Ada Lovelace"},
        "work": [
            {
                "name": "Analytical Engines",
                "position": "Lead Engineer",
                "location": "London",
                "startDate": "1844-01",
                "highlights": ["Led the programme."],
            },
            {
                "name": "Analytical Engines",
                "position": "Engineer",
                "location": "London",
                "startDate": "1842-01",
                "endDate": "1843-12",
                "highlights": ["Programmed the engine."],
            },
            {
                "name": "Royal Society",
                "position": "Fellow",
                "location": "London",
                "startDate": "1841-01",
                "endDate": "1841-12",
            },
        ],
    }

    html = render_html(resume)
    md = render_markdown(resume)

    assert html.count('class="company-name"') == 2
    assert html.count('class="role-title"') == 3
    assert html.count("Analytical Engines") == 1
    assert '<h4 class="role-title">Lead Engineer</h4>' in html
    assert '<h4 class="role-title">Fellow</h4>' in html
    assert '<span class="at">at</span>' not in html
    assert "Jan 1842 – Present" in html
    assert html.count("Jan 1841 – Dec 1841") == 1
    assert "### Analytical Engines (Jan 1842 – Present)" in md
    assert "#### Lead Engineer (Jan 1844 – Present)" in md
    assert "#### Engineer (Jan 1842 – Dec 1843)" in md
    assert "### Fellow — Royal Society (Jan 1841 – Dec 1841)" in md


def test_markdown_omits_sections_absent_from_the_document() -> None:
    md = render_markdown({"basics": {"name": "Ada"}})

    assert "Experience" not in md
    assert "Awards" not in md


def test_markdown_colophon_identifies_the_cut_and_the_build() -> None:
    md = render_markdown(
        {"basics": {"name": "Ada"}, "meta": {"source": "https://github.com/ada/cv"}},
        variant="acme",
        stamp=Stamp(version="2026.07.16+g942700c", modified="2026-07-16", dirty=False),
    )

    assert "acme cut" in md
    assert "2026.07.16+g942700c" in md
    assert "resume-as-code: https://github.com/ada/cv" in md


def test_markdown_without_provenance_has_no_dangling_rule() -> None:
    md = render_markdown({"basics": {"name": "Ada"}})

    assert "---" not in md
