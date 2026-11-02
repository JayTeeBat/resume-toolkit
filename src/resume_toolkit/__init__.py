"""Toolchain to validate a JSON Resume and render it to styled PDF/HTML."""

from importlib.metadata import version

__all__ = ["__version__"]

# Read from the installed metadata so it cannot drift from pyproject.toml.
__version__ = version("resume-toolkit")
