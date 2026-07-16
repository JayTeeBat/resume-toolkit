"""Loading and schema-validation of resume.json."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from .paths import RESUME_JSON, SCHEMA_JSON


class ValidationFailed(Exception):
    """resume.json does not satisfy the JSON Resume schema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} schema violation(s)")


def _json_path(error) -> str:
    """Render a jsonschema error's location as e.g. `work[2].startDate`."""
    path = ""
    for part in error.absolute_path:
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return path or "<root>"


def validate(resume: dict, schema_path: Path = SCHEMA_JSON) -> list[str]:
    """Return every schema violation in `resume`, as human-readable strings.

    Reports all errors rather than stopping at the first: editing a CV tends to
    introduce several mistakes at once, and fixing them one round-trip at a time
    is miserable.
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # FORMAT_CHECKER is opt-in: jsonschema treats `format` as a pure annotation
    # otherwise, which would let a malformed email or a dead profile URL through
    # silently. The schema declares `format` on 11 fields and those are exactly
    # the ones where a typo is invisible on the page but costly in practice.
    validator = Draft7Validator(schema, format_checker=Draft7Validator.FORMAT_CHECKER)
    return [
        f"{_json_path(error)}: {error.message}"
        for error in sorted(validator.iter_errors(resume), key=lambda e: list(e.absolute_path))
    ]


def load_resume(path: Path = RESUME_JSON, *, check: bool = True) -> dict:
    """Read resume.json, validating it against the vendored schema by default."""
    resume = json.loads(path.read_text(encoding="utf-8"))
    if check:
        errors = validate(resume)
        if errors:
            raise ValidationFailed(errors)
    return resume
