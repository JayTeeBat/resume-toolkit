"""Well-known locations inside the repo."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RESUME_JSON = REPO_ROOT / "resume.json"
VARIANTS_TOML = REPO_ROOT / "variants.toml"
SCHEMA_JSON = REPO_ROOT / "schema" / "resume.schema.json"
THEMES_DIR = REPO_ROOT / "themes"
DIST_DIR = REPO_ROOT / "dist"
