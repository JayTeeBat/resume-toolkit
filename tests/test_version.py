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


@pytest.mark.parametrize("sha", ["942700c", "942700c" + "0" * 33])
def test_stamp_is_calver_plus_commit(monkeypatch, sha) -> None:
    _fake_git(monkeypatch, {"log": "2026-07-16", "rev-parse": sha, "status": None})

    stamp = build_stamp()

    assert stamp == Stamp(
        version="2026.07.16+942700c",
        modified="2026-07-16",
        dirty=False,
        label="2026-07-16 · rev 942700c",
    )


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

    assert stamp is not None
    assert stamp.dirty is True
    assert stamp.modified == date.today().isoformat()
    assert stamp.version == f"{date.today():%Y.%m.%d}+942700c.dirty"
    assert stamp.label == f"{date.today().isoformat()} · rev 942700c (modified)"


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


def test_stamp_against_a_content_repository(tmp_path, monkeypatch) -> None:
    """Exercise real git on fictional content, independent of checkout history."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "resume.json"
    source.write_text("{}\n")
    for args in (
        ["init"],
        ["add", "resume.json"],
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "Fixture",
        ],
    ):
        subprocess.run(["git", *args], check=True, capture_output=True)
    stamp = build_stamp()
    assert stamp is not None
    assert stamp.version.startswith("20")
    assert "+g" not in stamp.version
    assert len(stamp.version.split("+")[1]) == 7
    assert not stamp.dirty
