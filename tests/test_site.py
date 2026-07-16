"""The published site: index.html plus every variant's artifacts.

These drive a real Chromium (the index links PDFs and reports their sizes, so
they have to exist), which is why they carry the slow marker.
"""

from __future__ import annotations

import pytest

from resume_toolkit.model import load_resume
from resume_toolkit.pdf import BrowserMissing
from resume_toolkit.site import build_site
from resume_toolkit.variants import load_variants


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


@pytest.mark.slow
def test_site_builds_an_index_and_every_variant(built) -> None:
    written, out = built
    names = {a.path.name for a in written}

    assert "index.html" in names
    for variant in load_variants():
        assert f"resume-{variant}.pdf" in names
        assert f"resume-{variant}.html" in names


@pytest.mark.slow
def test_index_links_resolve_to_files_that_exist(built) -> None:
    """A landing page whose download buttons 404 is worse than no landing page."""
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    for variant in load_variants():
        for target in (f"resume-{variant}.pdf", f"resume-{variant}.html"):
            assert f'href="{target}"' in index, f"index.html does not link {target}"
            assert (out / target).is_file()


@pytest.mark.slow
def test_index_carries_real_identity(built, resume) -> None:
    written, out = built
    index = (out / "index.html").read_text(encoding="utf-8")

    assert resume["basics"]["name"] in index
    assert resume["basics"]["label"] in index
