"""Variant filtering rules."""

from __future__ import annotations

import pytest

from resume_toolkit.variants import (
    UnknownVariant,
    Variant,
    apply_variant,
    get_variant,
    load_variants,
)

EVERYTHING = Variant("full", "", frozenset({"*"}))
UNTAGGED_ONLY = Variant("short", "", frozenset())
ENG = Variant("eng", "", frozenset({"eng"}))


def resume(**sections) -> dict:
    return {"basics": {"name": "Test"}, **sections}


def test_untagged_entries_survive_every_variant() -> None:
    data = resume(work=[{"name": "Core"}])

    for variant in (EVERYTHING, UNTAGGED_ONLY, ENG):
        assert apply_variant(data, variant)["work"] == [{"name": "Core"}]


def test_tagged_entry_is_dropped_when_its_tag_is_not_included() -> None:
    data = resume(work=[{"name": "Old", "x-tags": ["full"]}])

    assert "work" not in apply_variant(data, UNTAGGED_ONLY)


def test_tagged_entry_survives_when_a_tag_intersects() -> None:
    data = resume(work=[{"name": "Backend", "x-tags": ["eng", "misc"]}])

    assert apply_variant(data, ENG)["work"] == [{"name": "Backend"}]


def test_wildcard_includes_tagged_entries() -> None:
    data = resume(work=[{"name": "Old", "x-tags": ["obscure"]}])

    assert apply_variant(data, EVERYTHING)["work"] == [{"name": "Old"}]


def test_x_tags_are_stripped_from_output() -> None:
    """Themes must never have to know that variants exist."""
    data = resume(work=[{"name": "Core", "x-tags": ["eng"]}])

    assert apply_variant(data, ENG)["work"] == [{"name": "Core"}]


def test_emptied_section_is_removed_not_left_blank() -> None:
    """An empty list would render as a bare heading with nothing under it."""
    data = resume(work=[{"name": "Old", "x-tags": ["full"]}], skills=[{"name": "Kept"}])

    out = apply_variant(data, UNTAGGED_ONLY)

    assert "work" not in out
    assert out["skills"] == [{"name": "Kept"}]


def test_non_taggable_sections_pass_through_untouched() -> None:
    data = resume(work=[{"name": "Core"}])
    data["meta"] = {"version": "v1.0.0"}

    out = apply_variant(data, UNTAGGED_ONLY)

    assert out["basics"] == {"name": "Test"}
    assert out["meta"] == {"version": "v1.0.0"}


def test_apply_variant_does_not_mutate_the_input() -> None:
    data = resume(work=[{"name": "Old", "x-tags": ["full"]}])

    apply_variant(data, UNTAGGED_ONLY)

    assert data["work"] == [{"name": "Old", "x-tags": ["full"]}]


def test_repo_variants_toml_loads() -> None:
    variants = load_variants()

    assert "full" in variants
    assert variants["full"].includes_everything


def test_unknown_variant_names_the_known_ones() -> None:
    with pytest.raises(UnknownVariant, match="full"):
        get_variant("does-not-exist")
