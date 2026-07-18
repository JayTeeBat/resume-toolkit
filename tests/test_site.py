"""The published site: index.html plus every variant's artifacts.

These drive a real Chromium (the index links PDFs and reports their sizes, so
they have to exist), which is why they carry the slow marker.
"""

from __future__ import annotations

import pytest
from markupsafe import escape

from resume_toolkit import site as site_mod
from resume_toolkit.model import load_resume
from resume_toolkit.pdf import BrowserMissing
from resume_toolkit.site import build_site
from resume_toolkit.variants import Variant, load_variants


def _published() -> list[str]:
    return [name for name, v in load_variants().items() if v.publish]


def _unpublished() -> list[str]:
    return [name for name, v in load_variants().items() if not v.publish]


@pytest.fixture(scope="module")
def resume() -> dict:
    return load_resume()


@pytest.fixture(scope="module")
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


@pytest.mark.slow
def test_site_builds_an_index_and_every_published_variant(built) -> None:
    written, out = built
    names = {a.path.name for a in written}

    assert "index.html" in names
    for variant in _published():
        assert f"resume-{variant}.pdf" in names
        assert f"resume-{variant}.html" in names
        assert f"resume-{variant}.json" in names


@pytest.mark.slow
def test_unpublished_variants_never_reach_the_site(built) -> None:
    """The whole point of the flag: a private cut must leave no file to leak."""
    written, out = built
    names = {a.path.name for a in written}

    for variant in _unpublished():
        for fmt in ("pdf", "html", "json"):
            assert f"resume-{variant}.{fmt}" not in names
            assert not (out / f"resume-{variant}.{fmt}").exists()


@pytest.mark.slow
def test_index_links_resolve_to_files_that_exist(built) -> None:
    """A landing page whose download buttons 404 is worse than no landing page."""
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    for variant in _published():
        for fmt in ("pdf", "html", "json"):
            target = f"resume-{variant}.{fmt}"
            assert f'href="{target}"' in index, f"index.html does not link {target}"
            assert (out / target).is_file()


@pytest.mark.slow
def test_index_carries_real_identity(built, resume) -> None:
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    # The page is autoescaped HTML, so compare against the escaped form —
    # a label containing "&" appears as "&amp;".
    assert str(escape(resume["basics"]["name"])) in index
    assert str(escape(resume["basics"]["label"])) in index
