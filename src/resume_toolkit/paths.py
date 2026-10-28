"""Content belongs to the working directory; bundled assets belong to the package."""

from pathlib import Path

REPO_ROOT = Path(".")
RESUME_JSON = Path("resume.json")
VARIANTS_TOML = Path("variants.toml")
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
SCHEMA_JSON = ASSETS_DIR / "schema" / "resume.schema.json"
THEMES_DIR = ASSETS_DIR / "themes"
SITE_DIR = ASSETS_DIR / "site"
DIST_DIR = Path("dist")
