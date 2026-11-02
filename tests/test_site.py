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
from resume_toolkit.build import artifact_filename
from resume_toolkit.pdf import BrowserMissing
from resume_toolkit.site import build_site
from resume_toolkit.variants import Variant, load_variants


def _published() -> list[str]:
    return [
        name
        for name, v in load_variants(FIXTURES / "variants.toml").items()
        if v.publish
    ]


def _filename(resume: dict, variant: str, fmt: str) -> str:
    """The site's name for one artifact of the fixture's variants."""
    return artifact_filename(fmt, resume["basics"]["name"], variant, _published()[0])


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
        "html": "resume.html",
        "pdf": "Alex-Morgan-Resume.pdf",
        "json": "resume.json",
        "md": "resume.md",
        "size": "42 KB",
    }

    index = site_mod._render_index(resume, [card])

    assert '<a class="btn primary" href="resume.html">HTML</a>' in index
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
            **{
                fmt: artifact_filename(fmt, "Alex Morgan", name, names[0])
                for fmt in ("html", "pdf", "json", "md")
            },
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

    assert index.count('class="actions solo"') == 1
    assert "Other versions" not in index
    assert 'class="card' not in index
    assert "Short Version" not in index


def test_llms_txt_names_the_primary_cut_and_lists_every_cut(resume) -> None:
    llms = site_mod._render_llms(resume, _cards("one-page", "2-page", "full"))

    assert "primary published cut (one-page)" in llms
    for name in ("one-page", "2-page", "full"):
        assert artifact_filename("pdf", "Alex Morgan", name, "one-page") in llms
        assert f"The {name} cut" in llms


@pytest.mark.slow
def test_site_builds_an_index_and_every_published_variant(built, resume) -> None:
    written, out = built
    names = {a.path.name for a in written}

    assert "index.html" in names
    for variant in _published():
        for fmt in ("pdf", "html", "json", "md"):
            target = _filename(resume, variant, fmt)
            assert target in names


@pytest.mark.slow
def test_unpublished_variants_never_reach_the_site(built, resume) -> None:
    """The whole point of the flag: a private cut must leave no file to leak."""
    written, out = built
    names = {a.path.name for a in written}

    for variant in _unpublished():
        for fmt in ("pdf", "html", "json", "md"):
            target = _filename(resume, variant, fmt)
            assert target not in names
            assert not (out / target).exists()


@pytest.mark.slow
def test_index_links_resolve_to_files_that_exist(built, resume) -> None:
    """A landing page whose download buttons 404 is worse than no landing page."""
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    for variant in _published():
        for fmt in ("pdf", "html", "json", "md"):
            target = _filename(resume, variant, fmt)
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
def test_primary_cut_publishes_at_the_unsuffixed_addresses(built) -> None:
    """/resume.json and friends are the primary cut itself, not alias copies:
    one file per artifact, so nothing can drift, and no URL names the variant."""
    written, out = built
    primary = _published()[0]

    for fmt in ("html", "json", "md"):
        assert (out / f"resume.{fmt}").is_file()
        assert not (out / f"resume-{primary}.{fmt}").exists()
    paths = [a.path for a in written]
    assert len(paths) == len(set(paths)), "an artifact was written twice"
    published = json.loads((out / "resume.json").read_text(encoding="utf-8"))
    assert published["basics"]["name"]


@pytest.mark.slow
def test_every_link_on_the_front_matter_resolves(built, resume) -> None:
    """index.html, llms.txt and sitemap.xml all point at files that exist."""
    written, out = built
    base = resume["meta"]["canonical"].rstrip("/") + "/"
    index = (out / "index.html").read_text(encoding="utf-8")
    llms = (out / "llms.txt").read_text(encoding="utf-8")
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")

    links = re.findall(r'class="btn[^"]*" href="([^"]+)"', index)
    links += [u.removeprefix(base) for u in re.findall(r"\]\(([^)]+)\)", llms)]
    links += [u.removeprefix(base) for u in re.findall(r"<loc>([^<]+)</loc>", sitemap)]
    local = [link for link in links if not link.startswith(("http", "mailto:"))]
    assert "resume.html" in local
    assert "resume.json" in local
    for link in local:
        assert (out / (link or "index.html")).is_file(), link


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
        assert f"{base}{_filename(resume, variant, 'html')}" in locs


@pytest.mark.slow
def test_site_names_primary_and_alternative_pdfs(resume, tmp_path, monkeypatch) -> None:
    cuts = {
        name: Variant(name, "", frozenset({"*"}), publish=name != "private")
        for name in ("private", "2-page", "one-page", "full")
    }
    monkeypatch.setattr(site_mod, "load_variants", lambda: cuts)
    resume["basics"]["name"] = "Élodie Morgan"
    artifacts = build_site(resume, out_dir=tmp_path)
    filenames = {a.path.name for a in artifacts if a.variant in cuts}
    assert filenames == {
        "Elodie-Morgan-Resume.pdf",
        "resume.html",
        "resume.json",
        "resume.md",
        "Elodie-Morgan-Resume-One-Page.pdf",
        "resume-one-page.html",
        "resume-one-page.json",
        "resume-one-page.md",
        "Elodie-Morgan-Resume-Full.pdf",
        "resume-full.html",
        "resume-full.json",
        "resume-full.md",
    }
    index = (tmp_path / "index.html").read_text()
    llms = (tmp_path / "llms.txt").read_text()
    for filename in filenames:
        assert (tmp_path / filename).is_file()
        assert f'href="{filename}"' in index
        assert filename in llms
    assert not list(tmp_path.glob("resume-2-page.*"))
    assert not list(tmp_path.glob("resume-private.*"))


@pytest.mark.slow
def test_single_published_cut_has_no_version_label(resume, tmp_path, monkeypatch):
    from pypdf import PdfReader

    cuts = {
        name: Variant(name, "", frozenset({"*"}), publish=name == "2-page")
        for name in ("one-page", "2-page", "full")
    }
    monkeypatch.setattr(site_mod, "load_variants", lambda: cuts)
    artifacts = build_site(resume, out_dir=tmp_path)
    assert {a.variant for a in artifacts if a.fmt == "pdf"} == {"2-page"}
    for artifact in artifacts:
        if artifact.variant == "2-page" and artifact.fmt in {"pdf", "html", "md"}:
            text = (
                PdfReader(artifact.path).pages[0].extract_text()
                if artifact.fmt == "pdf"
                else artifact.path.read_text()
            )
            assert "2-Page Version" not in text
    index = (tmp_path / "index.html").read_text()
    assert index.count('class="actions solo"') == 1
    assert "Other versions" not in index
    for name in ("one-page", "full"):
        assert not list(tmp_path.glob(f"resume-{name}.*"))
        for filename in ("index.html", "sitemap.xml", "llms.txt"):
            assert f"resume-{name}" not in (tmp_path / filename).read_text()
    assert (tmp_path / "resume.json").is_file()
    assert not list(tmp_path.glob("resume-*"))


@pytest.mark.slow
@pytest.mark.parametrize("omitted", ["md", "json", "pdf", "html"])
def test_site_omits_unselected_formats(resume, tmp_path, monkeypatch, omitted):
    formats = tuple(fmt for fmt in ("pdf", "html", "json", "md") if fmt != omitted)
    cut = Variant("short", "Public cut", frozenset(), publish=True, formats=formats)
    monkeypatch.setattr(site_mod, "load_variants", lambda: {cut.name: cut})
    stale = artifact_filename(omitted, resume["basics"]["name"], "short", "short")
    (tmp_path / stale).write_text("previous build")
    written = build_site(resume, out_dir=tmp_path)
    names = {a.path.name for a in written}
    index = (tmp_path / "index.html").read_text()
    llms = (tmp_path / "llms.txt").read_text()
    sitemap = (tmp_path / "sitemap.xml").read_text()
    for fmt in ("pdf", "html", "json", "md"):
        name = artifact_filename(fmt, resume["basics"]["name"], "short", "short")
        assert (name in names) == (fmt != omitted)
        assert (tmp_path / name).exists() == (fmt != omitted)
        assert (f'href="{name}"' in index) == (fmt != omitted)
        if fmt != "json":
            assert (name in llms) == (fmt != omitted)
    assert ("PDF · " in index) == (omitted != "pdf")
    assert ("[resume.json]" in llms) == (omitted != "json")
    assert ("## Machine-readable" in llms) == (omitted != "json")
    assert ("resume.html" in sitemap) == (omitted != "html")
    assert not list(tmp_path.glob("resume-*"))
    title = f"{resume['basics']['name']} — Resume"
    assert llms.startswith(f"# {title}\n")
    assert f"<title>{title}</title>" in index
    assert f'property="og:title" content="{title}"' in index


def test_llms_lists_secondary_json_without_primary_alias(resume):
    cards = _cards("short", "full")
    del cards[0]["json"]
    llms = site_mod._render_llms(resume, cards)
    assert "[resume.json]" not in llms
    assert "[resume-full.json]" in llms
