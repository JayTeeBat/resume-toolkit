"""The published site: index.html plus every variant's artifacts.

These drive a real Chromium (the index links PDFs and reports their sizes, so
they have to exist), which is why they carry the slow marker.
"""

from __future__ import annotations

import json
import re

import pytest
from conftest import FIXTURES
from markupsafe import escape

from resume_toolkit import site as site_mod
from resume_toolkit.pdf import BrowserMissing, pdf_filename
from resume_toolkit.site import build_site
from resume_toolkit.variants import Variant, load_variants


def _published() -> list[str]:
    return [
        name
        for name, v in load_variants(FIXTURES / "variants.toml").items()
        if v.publish
    ]


def _unpublished() -> list[str]:
    return [
        name
        for name, v in load_variants(FIXTURES / "variants.toml").items()
        if not v.publish
    ]


@pytest.fixture
def built(resume, tmp_path_factory) -> tuple:
    out = tmp_path_factory.mktemp("site")
    try:
        return build_site(resume, out_dir=out), out
    except BrowserMissing as exc:
        pytest.skip(str(exc))


def test_build_site_refuses_when_nothing_is_publishable(monkeypatch, tmp_path) -> None:
    """No opted-in cut means no page — and it must say why, not build an empty one.

    Fast on purpose: it must raise before touching Chromium.
    """
    monkeypatch.setattr(
        site_mod,
        "load_variants",
        lambda: {"draft": Variant("draft", "", frozenset({"*"}), publish=False)},
    )

    with pytest.raises(ValueError, match="publish = true"):
        build_site({"basics": {"name": "Test"}}, out_dir=tmp_path)


def test_index_prioritises_html_and_opens_pdf_in_a_browser(resume) -> None:
    card = {
        "name": "short",
        "description": "Published CV",
        "html": "resume-short.html",
        "pdf": "Alex-Morgan-Resume.pdf",
        "json": "resume-short.json",
        "md": "resume-short.md",
        "size": "42 KB",
    }

    index = site_mod._render_index(resume, [card])

    assert '<a class="btn primary" href="resume-short.html">HTML</a>' in index
    assert (
        '<a class="btn" href="Alex-Morgan-Resume.pdf" '
        'target="_blank" rel="noopener">PDF</a>' in index
    )
    assert "download=" not in index
    assert index.index(card["html"]) < index.index(card["pdf"])
    assert index.index(card["pdf"]) < index.index(card["json"])
    assert index.index(card["json"]) < index.index(card["md"])


def _cards(*names: str) -> list[dict]:
    return [
        {
            "name": name,
            "description": f"The {name} cut",
            "html": f"resume-{name}.html",
            "pdf": pdf_filename("Alex Morgan", name, names[0]),
            "json": f"resume-{name}.json",
            "md": f"resume-{name}.md",
            "size": "42 KB",
        }
        for name in names
    ]


def test_index_leads_with_the_primary_cut_and_offers_the_rest(resume) -> None:
    """First published variant = primary card; the others follow, in file
    order, as alternatives with the same four actions."""
    index = site_mod._render_index(resume, _cards("one-page", "2-page", "full"))

    primary = index.index('class="card primary-card"')
    alternatives = index.index('class="alternatives"')
    assert primary < index.index("One-Page Version") < alternatives
    assert index.count('class="card primary-card"') == 1
    assert index.count('class="card alternative"') == 2
    assert alternatives < index.index("2-Page Version") < index.index("Full Version")
    for card in _cards("one-page", "2-page", "full"):
        targets = "|".join(
            re.escape(card[fmt]) for fmt in ("html", "pdf", "json", "md")
        )
        actions = re.findall(rf'href="(?:{targets})"[^>]*>(\w+)</a>', index)
        assert actions == ["HTML", "PDF", "JSON", "Markdown"]
        # Descriptions are author notes, kept for llms.txt but not shown.
        assert card["description"] not in index
    assert "Built from" not in index
    assert re.search(r"<footer>Updated \d{4}-\d{2}-\d{2}</footer>", index)


def test_index_with_one_cut_shows_actions_only(resume) -> None:
    index = site_mod._render_index(resume, _cards("short"))

    assert 'class="actions solo"' in index
    assert 'class="card' not in index
    assert "Short Version" not in index


def test_llms_txt_names_the_primary_cut_and_lists_every_cut(resume) -> None:
    llms = site_mod._render_llms(resume, _cards("one-page", "2-page", "full"))

    assert "primary published cut (one-page)" in llms
    for name in ("one-page", "2-page", "full"):
        assert pdf_filename("Alex Morgan", name, "one-page") in llms
        assert f"The {name} cut" in llms


@pytest.mark.slow
def test_site_builds_an_index_and_every_published_variant(built, resume) -> None:
    written, out = built
    names = {a.path.name for a in written}

    assert "index.html" in names
    for variant in _published():
        for fmt in ("pdf", "html", "json", "md"):
            target = (
                pdf_filename(resume["basics"]["name"], variant, _published()[0])
                if fmt == "pdf"
                else f"resume-{variant}.{fmt}"
            )
            assert target in names


@pytest.mark.slow
def test_unpublished_variants_never_reach_the_site(built, resume) -> None:
    """The whole point of the flag: a private cut must leave no file to leak."""
    written, out = built
    names = {a.path.name for a in written}

    for variant in _unpublished():
        for fmt in ("pdf", "html", "json", "md"):
            target = (
                pdf_filename(resume["basics"]["name"], variant, _published()[0])
                if fmt == "pdf"
                else f"resume-{variant}.{fmt}"
            )
            assert target not in names
            assert not (out / target).exists()


@pytest.mark.slow
def test_index_links_resolve_to_files_that_exist(built, resume) -> None:
    """A landing page whose download buttons 404 is worse than no landing page."""
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    for variant in _published():
        for fmt in ("pdf", "html", "json", "md"):
            target = (
                pdf_filename(resume["basics"]["name"], variant, _published()[0])
                if fmt == "pdf"
                else f"resume-{variant}.{fmt}"
            )
            assert f'href="{target}"' in index, f"index.html does not link {target}"
            assert (out / target).is_file()
            if fmt == "pdf":
                assert f"PDF · {(out / target).stat().st_size / 1024:.0f} KB" in index
                assert target in (out / "llms.txt").read_text()
                assert not (out / f"resume-{variant}.pdf").exists()


@pytest.mark.slow
def test_index_carries_real_identity(built, resume) -> None:
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    # The page is autoescaped HTML, so compare against the escaped form —
    # a label containing "&" appears as "&amp;".
    assert str(escape(resume["basics"]["name"])) in index
    assert str(escape(resume["basics"]["label"])) in index


@pytest.mark.slow
def test_canonical_resume_json_alias_matches_the_primary_cut(built) -> None:
    """/resume.json is the guessable machine address. Byte-identical to the
    primary published cut, so the alias and the named file can never drift."""
    written, out = built
    primary = _published()[0]
    alias = out / "resume.json"

    assert alias.is_file()
    assert alias.read_bytes() == (out / f"resume-{primary}.json").read_bytes()


@pytest.mark.slow
def test_llms_txt_points_agents_at_the_canonical_json(built, resume) -> None:
    written, out = built
    llms = (out / "llms.txt").read_text(encoding="utf-8")

    assert llms.startswith(f"# {resume['basics']['name']}")
    assert "resume.json" in llms
    # Plain text, not autoescaped HTML: a label's "&" must survive as "&".
    assert "&amp;" not in llms


@pytest.mark.slow
def test_index_head_carries_link_preview_and_person_markup(built, resume) -> None:
    """og: tags decide what a pasted link looks like; the JSON-LD Person is
    what search engines index. Both must describe the real person."""
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    assert 'property="og:title"' in index
    assert 'property="og:description"' in index

    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', index, re.S
    )
    assert match, "index.html has no JSON-LD block"
    person = json.loads(match.group(1))
    assert person["@type"] == "Person"
    assert person["name"] == resume["basics"]["name"]
    assert person["jobTitle"] == resume["basics"]["label"]

    assert 'rel="icon"' in index


@pytest.mark.slow
def test_404_routes_the_lost_back_to_the_index(built, resume) -> None:
    """Pages serves 404.html for any dead path — a bookmarked artifact of an
    old cut must land on an exit, not a GitHub-branded wall."""
    written, out = built
    page = (out / "404.html").read_text(encoding="utf-8")

    canonical = resume["meta"]["canonical"]
    assert f'href="{canonical}"' in page
    # A dead-end page must never rank in search results.
    assert 'name="robots" content="noindex"' in page


@pytest.mark.slow
def test_robots_allows_all_and_names_the_sitemap(built, resume) -> None:
    written, out = built
    robots = (out / "robots.txt").read_text(encoding="utf-8")

    assert "User-agent: *" in robots
    assert "Allow: /" in robots
    assert f"Sitemap: {resume['meta']['canonical'].rstrip('/')}/sitemap.xml" in robots


@pytest.mark.slow
def test_sitemap_lists_the_index_and_every_published_page(built, resume) -> None:
    """Parsed as XML, not grepped: a malformed sitemap is silently ignored by
    crawlers, which is the failure mode this test exists to prevent."""
    import xml.etree.ElementTree as ET

    written, out = built
    tree = ET.parse(out / "sitemap.xml")
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    locs = {el.text for el in tree.iter(f"{ns}loc")}

    base = resume["meta"]["canonical"].rstrip("/") + "/"
    assert base in locs
    for variant in _published():
        assert f"{base}resume-{variant}.html" in locs


@pytest.mark.slow
def test_site_names_primary_and_alternative_pdfs(resume, tmp_path, monkeypatch) -> None:
    cuts = {
        name: Variant(name, "", frozenset({"*"}), publish=name != "private")
        for name in ("private", "2-page", "one-page", "full")
    }
    monkeypatch.setattr(site_mod, "load_variants", lambda: cuts)
    resume["basics"]["name"] = "Élodie Morgan"
    artifacts = build_site(resume, out_dir=tmp_path)
    filenames = {a.path.name for a in artifacts if a.fmt == "pdf"}
    assert filenames == {
        "Elodie-Morgan-Resume.pdf",
        "Elodie-Morgan-Resume-One-Page.pdf",
        "Elodie-Morgan-Resume-Full.pdf",
    }
    index = (tmp_path / "index.html").read_text()
    llms = (tmp_path / "llms.txt").read_text()
    for filename in filenames:
        assert (tmp_path / filename).is_file()
        assert f'href="{filename}"' in index
        assert filename in llms
