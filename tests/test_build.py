"""End-to-end build smoke tests.

These drive a real Chromium, so they are the slowest tests here by far — but
they are the only ones that would catch the PDF pipeline breaking.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from conftest import FIXTURES

from resume_toolkit.build import artifact_filename, build_variant
from resume_toolkit.model import validate
from resume_toolkit.pdf import BrowserMissing
from resume_toolkit.variants import get_variant

A4_MM = (210, 297)


@pytest.mark.parametrize(
    ("fmt", "variant", "primary", "expected"),
    [
        ("html", "2-page", "2-page", "resume.html"),
        ("json", "2-page", "2-page", "resume.json"),
        ("md", "2-page", "2-page", "resume.md"),
        ("pdf", "2-page", "2-page", "Alex-Morgan-Resume.pdf"),
        ("html", "full", "2-page", "resume-full.html"),
        ("json", "full", "2-page", "resume-full.json"),
        ("md", "full", "2-page", "resume-full.md"),
        ("pdf", "full", "2-page", "Alex-Morgan-Resume-Full.pdf"),
        ("html", "2-page", None, "resume-2-page.html"),
        ("json", "2-page", None, "resume-2-page.json"),
        ("md", "2-page", None, "resume-2-page.md"),
        ("pdf", "2-page", None, "Alex-Morgan-Resume-2-Page.pdf"),
    ],
)
def test_primary_cut_is_unsuffixed_in_every_format(
    fmt, variant, primary, expected
) -> None:
    assert artifact_filename(fmt, "Alex Morgan", variant, primary) == expected


def test_build_writes_the_primary_cut_at_unsuffixed_names(resume, tmp_path) -> None:
    variants = FIXTURES / "variants.toml"
    for name in ("short", "full"):
        build_variant(
            resume,
            get_variant(name, variants),
            formats=("html", "json", "md"),
            primary_variant="short",
            out_dir=tmp_path,
        )
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "resume-full.html",
        "resume-full.json",
        "resume-full.md",
        "resume.html",
        "resume.json",
        "resume.md",
    ]


def test_html_build_is_self_contained(resume, tmp_path) -> None:
    written = build_variant(
        resume,
        get_variant("full", FIXTURES / "variants.toml"),
        formats=("html",),
        out_dir=tmp_path,
    )

    assert len(written) == 1
    html = written[0].path.read_text(encoding="utf-8")
    assert "url('data:font/woff2;base64," in html
    # Nothing may point at a file the export doesn't carry with it.
    assert "fonts/source-sans-3" not in html


def test_short_variant_drops_tagged_entries(resume, tmp_path) -> None:
    """Derives its expectation from resume.json rather than hardcoding content.

    An earlier version asserted on a literal company name and broke the moment
    the real CV replaced the placeholder. The behaviour under test is the
    filtering, not any particular employer.
    """
    short = get_variant("short", FIXTURES / "variants.toml")
    dropped = [
        w
        for w in resume["work"]
        if w.get("x-tags") and not (set(w["x-tags"]) & short.include)
    ]
    kept = [w for w in resume["work"] if not w.get("x-tags")]
    assert dropped, "resume.json must have both tagged and untagged work to test this"

    assert kept, "resume.json must have untagged work to test this"

    full_html = build_variant(
        resume,
        get_variant("full", FIXTURES / "variants.toml"),
        formats=("html",),
        out_dir=tmp_path,
    )[0].path.read_text(encoding="utf-8")
    short_html = build_variant(resume, short, formats=("html",), out_dir=tmp_path)[
        0
    ].path.read_text(encoding="utf-8")

    for entry in dropped:
        assert entry["position"] in full_html
        assert entry["position"] not in short_html, (
            f"{entry['position']} leaked into short"
        )

    for entry in kept:
        assert entry["position"] in short_html, (
            f"untagged {entry['position']} missing from short"
        )


def _keys_everywhere(node) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _keys_everywhere(v)}
    if isinstance(node, list):
        return {k for v in node for k in _keys_everywhere(v)}
    return set()


def test_json_build_is_variant_conform(resume, tmp_path) -> None:
    """The machine-readable artifact must say exactly what the rendered cut
    says: entries and bullets the variant drops are gone, and none of the
    variant machinery (x-tags, x-highlights) rides along to reveal them.
    """
    short = get_variant("short", FIXTURES / "variants.toml")
    written = build_variant(resume, short, formats=("json",), out_dir=tmp_path)

    assert [(a.variant, a.fmt) for a in written] == [("short", "json")]
    data = json.loads(written[0].path.read_text(encoding="utf-8"))

    keys = _keys_everywhere(data)
    assert "x-tags" not in keys
    assert "x-highlights" not in keys

    dropped = [
        w
        for w in resume["work"]
        if w.get("x-tags") and not (set(w["x-tags"]) & short.include)
    ]
    assert dropped, (
        "resume.json must have work entries tagged out of short to test this"
    )
    kept_positions = {w.get("position") for w in data.get("work", [])}
    for entry in dropped:
        assert entry["position"] not in kept_positions, (
            f"{entry['position']} leaked into the JSON"
        )


def test_json_build_is_a_valid_json_resume_with_provenance(
    resume, tmp_path, monkeypatch
) -> None:
    """Machine-ready means a consumer can trust the schema and date the file."""
    from resume_toolkit.version import Stamp

    monkeypatch.setattr(
        "resume_toolkit.build.build_stamp",
        lambda: Stamp(
            "2026.01.01+1234567", "2026-01-01", False, "2026-01-01 · rev 1234567"
        ),
    )
    written = build_variant(
        resume,
        get_variant("short", FIXTURES / "variants.toml"),
        formats=("json",),
        out_dir=tmp_path,
    )
    data = json.loads(written[0].path.read_text(encoding="utf-8"))

    assert validate(data) == []
    # A known content stamp is propagated to machine-readable output.
    meta = data.get("meta") or {}
    assert meta["version"] == "2026.01.01+1234567"
    assert "lastModified" in meta


def test_markdown_build_writes_the_variant_cut(resume, tmp_path) -> None:
    """Same conformity bar as the JSON: the paste-ready cut must not carry
    what the variant drops."""
    short = get_variant("short", FIXTURES / "variants.toml")
    written = build_variant(resume, short, formats=("md",), out_dir=tmp_path)

    assert [(a.variant, a.fmt) for a in written] == [("short", "md")]
    md = written[0].path.read_text(encoding="utf-8")

    assert md.startswith(f"# {resume['basics']['name']}")
    dropped = [
        w
        for w in resume["work"]
        if w.get("x-tags") and not (set(w["x-tags"]) & short.include)
    ]
    for entry in dropped:
        assert entry["position"] not in md, (
            f"{entry['position']} leaked into the Markdown"
        )


@pytest.mark.slow
def test_pdf_build_produces_an_a4_document_with_extractable_text(
    resume, tmp_path
) -> None:
    pypdf = pytest.importorskip("pypdf")

    try:
        written = build_variant(
            resume,
            get_variant("full", FIXTURES / "variants.toml"),
            formats=("pdf",),
            out_dir=tmp_path,
        )
    except BrowserMissing as exc:
        pytest.skip(str(exc))

    path = written[0].path
    assert path.read_bytes().startswith(b"%PDF-")

    page = pypdf.PdfReader(str(path)).pages[0]
    width = float(page.mediabox.width) / 72 * 25.4
    height = float(page.mediabox.height) / 72 * 25.4
    assert width == pytest.approx(A4_MM[0], abs=1)
    assert height == pytest.approx(A4_MM[1], abs=1)

    # An unextractable text layer would make the CV unreadable to applicant
    # tracking systems, which is a silent and total failure.
    text = page.extract_text()
    assert resume["basics"]["name"] in text
    assert "�" not in text, "text layer lost characters"


@pytest.mark.slow
@pytest.mark.parametrize("variant", ["one-page", "2-page", "full"])
@pytest.mark.parametrize("dirty", [False, True])
@pytest.mark.parametrize("primary", [None, "2-page"])
def test_pdf_repeats_one_footer_with_page_numbers_on_every_page(
    resume, tmp_path, monkeypatch, variant, dirty, primary
) -> None:
    """Each page names the cut, the build and where the latest copy lives, and
    numbers itself; the text layer reads body first, footer last, once."""
    pypdf = pytest.importorskip("pypdf")
    from resume_toolkit.version import Stamp

    label = "2026-01-01 · rev 1234567" + (" (modified)" if dirty else "")
    monkeypatch.setattr(
        "resume_toolkit.build.build_stamp",
        lambda: Stamp(
            "2026.01.01+1234567" + (".dirty" if dirty else ""),
            "2026-01-01",
            dirty,
            label,
        ),
    )
    resume["work"][0]["highlights"] *= 60
    try:
        written = build_variant(
            resume,
            replace(get_variant("short", FIXTURES / "variants.toml"), name=variant),
            primary_variant=primary,
            formats=("pdf", "html", "md"),
            out_dir=tmp_path,
        )
    except BrowserMissing as exc:
        pytest.skip(str(exc))

    pages = pypdf.PdfReader(str(next(a.path for a in written if a.fmt == "pdf"))).pages
    assert len(pages) >= 2
    version = f"{variant.title()} Version"
    prefix = f"{version} · " if variant != primary else ""
    footer = f"{prefix}{label} · latest at example.com/cv"
    for artifact in written:
        if artifact.fmt in {"html", "md"}:
            text = artifact.path.read_text()
            assert (version in text) == (variant != primary)
            if artifact.fmt == "html":
                row = text.split('<footer class="colophon footer-row">')[1]
                assert not row.lstrip().startswith('<span class="sep"')
                assert '<span class="field"></span>' not in row
            else:
                assert not text.split("---")[-1].strip().startswith("·")
    for number, page in enumerate(pages, start=1):
        lines = page.extract_text().splitlines()
        assert lines[-1] == f"{footer} · {number} / {len(pages)}"
        assert sum(footer in line for line in lines) == 1
        # The canonical address stays clickable on every page.
        uris = [a.get_object()["/A"].get("/URI") for a in page.get("/Annots") or []]
        assert "https://example.com/cv/" in uris
    text = "".join(page.extract_text() for page in pages)
    # Body text is laid out once: the footer adds no second copy of anything.
    assert text.count(resume["basics"]["name"]) == 1
    assert text.count("Example College") == 1


@pytest.mark.slow
@pytest.mark.parametrize(
    ("name", "keywords"),
    [("short", "Python, SQL, Rust"), ("full", "Python, SQL, Rust, Kubernetes")],
)
def test_pdf_metadata_uses_the_filtered_cut(resume, tmp_path, name, keywords) -> None:
    from pypdf import PdfReader

    resume["skills"] = [
        {"name": "Core", "keywords": ["Python", "SQL", "Python"]},
        {"name": "Delivery", "keywords": ["Rust", "SQL"]},
        {"name": "Specialist", "keywords": ["Kubernetes"], "x-tags": ["full"]},
    ]
    written = build_variant(
        resume,
        get_variant(name, FIXTURES / "variants.toml"),
        formats=("pdf", "html"),
        out_dir=tmp_path,
        primary_variant="short",
    )
    pdf = next(a.path for a in written if a.fmt == "pdf")
    html = next(a.path.read_text() for a in written if a.fmt == "html")
    metadata = PdfReader(pdf).metadata
    assert metadata is not None
    title = f"{resume['basics']['name']} — Resume"
    assert f"<title>{title}</title>" in html
    assert metadata.title == title
    assert metadata.author == resume["basics"]["name"]
    assert metadata.subject == resume["basics"]["label"]
    assert metadata["/Keywords"] == keywords
