"""Build provenance derived from git.

The point of deriving the stamp is that it cannot drift out of date the way the
hand-written meta block did, so these tests are mostly about the cases where it
would be tempting to invent an answer instead of admitting there isn't one.
"""

from __future__ import annotations

import subprocess

import pytest

from resume_toolkit import version as ver
from resume_toolkit.version import Stamp, build_stamp


def _fake_git(monkeypatch, mapping: dict[str, str | None]) -> None:
    """Stub _git by matching on its first argument (log/rev-parse/status)."""
    monkeypatch.setattr(ver, "_git", lambda *args: mapping.get(args[0]))


def test_stamp_is_calver_plus_commit(monkeypatch) -> None:
    _fake_git(monkeypatch, {"log": "2026-07-16", "rev-parse": "942700c", "status": None})

    stamp = build_stamp()

    assert stamp == Stamp(version="2026.07.16+g942700c", modified="2026-07-16", dirty=False)


def test_uncommitted_edits_are_marked_and_dated_today(monkeypatch) -> None:
    """A dirty tree means the hash does not describe the file. Say so.

    The commit date would understate an edit made after it, which is exactly the
    drift the hand-maintained lastModified suffered from.
    """
    from datetime import date

    _fake_git(
        monkeypatch,
        {"log": "2026-07-16", "rev-parse": "942700c", "status": " M resume.json"},
    )

    stamp = build_stamp()

    assert stamp.dirty is True
    assert stamp.modified == date.today().isoformat()
    assert stamp.version.endswith("-dirty")
    assert "g942700c" in stamp.version


def test_no_stamp_rather_than_a_fabricated_one(monkeypatch) -> None:
    """No git, no repo, no history -> None. A CV still builds; it just cannot
    claim provenance it does not have."""
    _fake_git(monkeypatch, {})

    assert build_stamp() is None


def test_git_failure_is_not_fatal(monkeypatch) -> None:
    """git present but exiting non-zero (e.g. not a repository) must not raise."""

    def boom(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(subprocess, "run", boom)

    assert build_stamp() is None


def test_git_missing_entirely_is_not_fatal(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", boom)

    assert build_stamp() is None


@pytest.mark.slow
def test_stamp_against_the_real_repo() -> None:
    """The stub above proves the logic; this proves the git invocations are real.

    A typo in a --format string would pass every mocked test and produce garbage
    on every actual build.
    """
    stamp = build_stamp()

    assert stamp is not None, "the repo is a git checkout, so a stamp must exist"
    assert stamp.version.startswith("20"), stamp.version
    assert "+g" in stamp.version
