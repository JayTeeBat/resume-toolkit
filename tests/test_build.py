"""End-to-end build smoke tests.

These drive a real Chromium, so they are the slowest tests here by far — but
they are the only ones that would catch the PDF pipeline breaking.
"""

from __future__ import annotations

import json

import pytest

from resume_toolkit.build import build_variant
from resume_toolkit.model import load_resume, validate
from resume_toolkit.pdf import BrowserMissing
from resume_toolkit.variants import get_variant

A4_MM = (210, 297)


@pytest.fixture(scope="module")
def resume() -> dict:
    return load_resume()


def test_html_build_is_self_contained(resume, tmp_path) -> None:
    written = build_variant(
        resume, get_variant("full"), formats=("html",), out_dir=tmp_path
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
    short = get_variant("short")
    dropped = [
        w for w in resume["work"]
        if w.get("x-tags") and not (set(w["x-tags"]) & short.include)
    ]
    kept = [w for w in resume["work"] if not w.get("x-tags")]
    assert dropped and kept, "resume.json must have both tagged and untagged work to test this"

    full_html = build_variant(
        resume, get_variant("full"), formats=("html",), out_dir=tmp_path
    )[0].path.read_text(encoding="utf-8")
    short_html = build_variant(
        resume, short, formats=("html",), out_dir=tmp_path
    )[0].path.read_text(encoding="utf-8")

    for entry in dropped:
        assert entry["position"] in full_html
        assert entry["position"] not in short_html, f"{entry['position']} leaked into short"

    for entry in kept:
        assert entry["position"] in short_html, f"untagged {entry['position']} missing from short"


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
    short = get_variant("short")
    written = build_variant(resume, short, formats=("json",), out_dir=tmp_path)

    assert [(a.variant, a.fmt) for a in written] == [("short", "json")]
    data = json.loads(written[0].path.read_text(encoding="utf-8"))

    keys = _keys_everywhere(data)
    assert "x-tags" not in keys
    assert "x-highlights" not in keys

    dropped = [
        w for w in resume["work"]
        if w.get("x-tags") and not (set(w["x-tags"]) & short.include)
    ]
    assert dropped, "resume.json must have work entries tagged out of short to test this"
    kept_positions = {w.get("position") for w in data.get("work", [])}
    for entry in dropped:
        assert entry["position"] not in kept_positions, f"{entry['position']} leaked into the JSON"


def test_json_build_is_a_valid_json_resume_with_provenance(resume, tmp_path) -> None:
    """Machine-ready means a consumer can trust the schema and date the file."""
    written = build_variant(resume, get_variant("short"), formats=("json",), out_dir=tmp_path)
    data = json.loads(written[0].path.read_text(encoding="utf-8"))

    assert validate(data) == []
    # In a git checkout the stamp always exists; only a tarball build may omit it.
    meta = data.get("meta") or {}
    assert "version" in meta and "lastModified" in meta


@pytest.mark.slow
def test_pdf_build_produces_an_a4_document_with_extractable_text(resume, tmp_path) -> None:
    pypdf = pytest.importorskip("pypdf")

    try:
        written = build_variant(
            resume, get_variant("full"), formats=("pdf",), out_dir=tmp_path
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
