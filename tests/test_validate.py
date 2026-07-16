"""The real resume.json must satisfy the schema.

This is the test that earns its keep: it turns CI into a guard against a
typo'd CV.
"""

from __future__ import annotations

import json

import pytest

from resume_toolkit.model import ValidationFailed, load_resume, validate
from resume_toolkit.paths import RESUME_JSON


def test_repo_resume_is_valid() -> None:
    assert validate(json.loads(RESUME_JSON.read_text(encoding="utf-8"))) == []


def test_load_resume_returns_the_document() -> None:
    resume = load_resume()
    assert resume["basics"]["name"]


def test_bad_date_is_reported_with_its_json_path(tmp_path) -> None:
    resume = json.loads(RESUME_JSON.read_text(encoding="utf-8"))
    resume["work"][0]["startDate"] = "not-a-date"

    errors = validate(resume)

    assert any("work[0].startDate" in e for e in errors), errors


def test_all_violations_are_reported_not_just_the_first() -> None:
    resume = json.loads(RESUME_JSON.read_text(encoding="utf-8"))
    resume["work"][0]["startDate"] = "not-a-date"
    resume["basics"]["email"] = "not-an-email"

    errors = validate(resume)

    assert len(errors) >= 2, errors
    assert any("startDate" in e for e in errors)
    assert any("email" in e for e in errors)


def test_load_resume_raises_on_invalid_document(tmp_path) -> None:
    broken = tmp_path / "resume.json"
    broken.write_text(json.dumps({"basics": {"email": "nope"}}), encoding="utf-8")

    with pytest.raises(ValidationFailed) as excinfo:
        load_resume(broken)

    assert excinfo.value.errors


def test_x_tags_do_not_break_schema_validity() -> None:
    """The whole variants design rests on additionalProperties: true."""
    resume = json.loads(RESUME_JSON.read_text(encoding="utf-8"))
    resume["work"][0]["x-tags"] = ["anything", "at", "all"]

    assert validate(resume) == []
