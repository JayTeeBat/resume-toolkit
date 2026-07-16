"""Build provenance: which cut of the CV this is, and which commit produced it.

Version metadata written by hand rots. The `meta` block this replaced carried a
`version` set once and never bumped across a full CV rewrite, and a
`lastModified` reading midnight on a day the file was actually touched at 22:33.
Nothing forced either to be true, so neither was. Git already knows the answers,
so derive them at build time instead: a document cannot record its own commit
hash, but the build that reads it can.

CalVer, not SemVer: a CV has no consumers and no compatibility contract, so
major/minor/patch would be a judgement call on every edit with nothing riding on
the outcome. A date answers the only question a reader has, which is how current
this is. The short hash rides along so any PDF in the wild can be rebuilt
exactly.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .paths import REPO_ROOT, RESUME_JSON


@dataclass(frozen=True)
class Stamp:
    #: CalVer + commit, e.g. "2026.07.16+g942700c" or "...-dirty".
    version: str
    #: ISO date the content last changed.
    modified: str
    #: True when the source has uncommitted edits, so the hash alone is a lie.
    dirty: bool


def _git(*args: str) -> str | None:
    """Run a git command, or return None if git or the repo is unavailable.

    Best-effort by design: a tarball download or a git-less machine should still
    build a CV, just without provenance. A missing stamp is honest; a fabricated
    one is not.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def build_stamp(source: Path = RESUME_JSON) -> Stamp | None:
    """Describe the CV content as of now, or None if git cannot say.

    The date tracks `source` rather than HEAD: restyling the theme does not make
    the CV's content newer, and claiming otherwise would be the same lie the
    hand-written `lastModified` told. The hash tracks HEAD, because that is what
    you would check out to reproduce the build.
    """
    committed = _git("log", "-1", "--format=%cs", "--", str(source))
    sha = _git("rev-parse", "--short", "HEAD")
    if not committed or not sha:
        return None

    dirty = bool(_git("status", "--porcelain", "--", str(source)))
    # Uncommitted edits are by definition newer than the last commit, so the
    # commit date would understate them. Today is the truthful answer, and
    # -dirty says the hash does not fully describe this file.
    modified = date.today().isoformat() if dirty else committed

    version = f"{modified.replace('-', '.')}+g{sha}"
    if dirty:
        version += "-dirty"
    return Stamp(version=version, modified=modified, dirty=dirty)
