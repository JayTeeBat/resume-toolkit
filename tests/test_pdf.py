"""Portable filenames and metadata that leave the printed pages alone."""

from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

from resume_toolkit.pdf import document_metadata, pdf_filename, write_metadata


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Alex Morgan", "Alex-Morgan"),
        ("  Alex  Morgan ", "Alex-Morgan"),
        ("Élodie Muñoz", "Elodie-Munoz"),
        ("Anne-Marie O'Neil!", "Anne-Marie-ONeil"),
        ("A/B.C_2", "ABC2"),
    ],
)
def test_pdf_filename_slug(name, slug) -> None:
    assert pdf_filename(name, "2-page", "2-page") == f"{slug}-Resume.pdf"


@pytest.mark.parametrize("name", ["", "  ", "!!!", "中文"])
def test_empty_name_slug_fails(name) -> None:
    with pytest.raises(ValueError, match="basics.name.*nonempty ASCII"):
        pdf_filename(name, "full")


@pytest.mark.parametrize(
    ("variant", "primary", "suffix"),
    [
        ("2-page", "2-page", ""),
        ("one-page", "2-page", "-One-Page"),
        ("full", "2-page", "-Full"),
        ("2-page", None, "-2-Page"),
    ],
)
def test_primary_and_alternative_filenames(variant, primary, suffix) -> None:
    assert (
        pdf_filename("Alex Morgan", variant, primary)
        == f"Alex-Morgan-Resume{suffix}.pdf"
    )


def test_metadata_with_optional_fields_absent() -> None:
    assert document_metadata({}) == {"/Author": "", "/Subject": "", "/Keywords": ""}


def test_metadata_postprocessing_is_deterministic_and_preserves_pages(tmp_path) -> None:
    original = PdfWriter()
    original.add_blank_page(width=210, height=297)
    original.add_metadata(
        {"/Title": "Alex Morgan — Resume", "/CreationDate": "D:20260101000000Z"}
    )
    stream = BytesIO()
    original.write(stream)
    outputs = []
    for index in range(2):
        path = tmp_path / f"{index}.pdf"
        path.write_bytes(stream.getvalue())
        write_metadata(path, {"/Author": "Alex Morgan"})
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1]
    reader = PdfReader(BytesIO(outputs[0]))
    assert reader.metadata is not None
    assert reader.metadata.title == "Alex Morgan — Resume"
    assert reader.metadata["/CreationDate"] == "D:20260101000000Z"
    assert "/ID" not in reader.trailer
    assert len(reader.pages) == 1
    assert reader.pages[0].mediabox == original.pages[0].mediabox
