"""`resume` command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .build import build_variant
from .model import ValidationFailed, load_resume
from .paths import DIST_DIR, RESUME_JSON
from .pdf import BrowserMissing
from .render import UnknownTheme
from .site import build_site
from .variants import UnknownVariant, get_variant, load_variants

app = typer.Typer(
    add_completion=False,
    help="Validate resume.json and render it to styled PDF/HTML.",
    no_args_is_help=True,
)

err = typer.style("error", fg=typer.colors.RED, bold=True)
ok = typer.style("ok", fg=typer.colors.GREEN, bold=True)


def _load_or_exit(path: Path = RESUME_JSON) -> dict:
    try:
        return load_resume(path)
    except FileNotFoundError:
        typer.echo(f"{err}: no resume at {path}")
        raise typer.Exit(2) from None
    except ValidationFailed as exc:
        typer.echo(f"{err}: {path.name} does not satisfy the JSON Resume schema\n")
        for problem in exc.errors:
            # ASCII deliberately: a Windows cp1252 console mangles "·" to "?".
            typer.echo(f"  - {problem}")
        typer.echo(f"\n{len(exc.errors)} violation(s).")
        raise typer.Exit(1) from None


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Resume file to check.")] = RESUME_JSON,
) -> None:
    """Check resume.json against the vendored JSON Resume schema."""
    _load_or_exit(path)
    typer.echo(f"{ok}: {path.name} is a valid JSON Resume")


@app.command(name="variants")
def list_variants() -> None:
    """List the variants defined in variants.toml."""
    for variant in load_variants().values():
        tags = (
            "everything"
            if variant.includes_everything
            else (", ".join(sorted(variant.include)) or "untagged entries only")
        )
        name = typer.style(variant.name, bold=True)
        typer.echo(f"{name}\n    {variant.description}\n    includes: {tags}")


@app.command()
def build(
    variant: Annotated[
        str | None,
        typer.Option("--variant", "-v", help="Variant to build. Default: all of them."),
    ] = None,
    theme: Annotated[
        str, typer.Option("--theme", "-t", help="Theme directory name.")
    ] = "classic",
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="pdf, html, json, md, or all."),
    ] = "all",
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Output directory.")
    ] = DIST_DIR,
) -> None:
    """Render resume.json to dist/."""
    if fmt not in {"pdf", "html", "json", "md", "all"}:
        typer.echo(f"{err}: --format must be pdf, html, json, md or all (got {fmt!r})")
        raise typer.Exit(2) from None
    formats = ("pdf", "html", "json", "md") if fmt == "all" else (fmt,)

    resume = _load_or_exit()

    try:
        targets = [get_variant(variant)] if variant else list(load_variants().values())
    except UnknownVariant as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2) from None

    if not targets:
        typer.echo(f"{err}: variants.toml defines no variants")
        raise typer.Exit(2) from None

    try:
        for target in targets:
            for artifact in build_variant(
                resume, target, theme=theme, formats=formats, out_dir=out
            ):
                size = artifact.path.stat().st_size
                typer.echo(f"{ok}: {artifact.path} ({size / 1024:.0f} KB)")
    except (UnknownTheme, BrowserMissing) as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2) from None


@app.command()
def site(
    theme: Annotated[
        str, typer.Option("--theme", "-t", help="Theme directory name.")
    ] = "classic",
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Output directory.")
    ] = DIST_DIR,
) -> None:
    # ASCII deliberately, as in _load_or_exit: a Windows cp1252 console mangles
    # "-" typed as an em-dash into "?" when typer prints this help text.
    """Build every variant plus an index.html - what CI publishes to Pages."""
    resume = _load_or_exit()

    try:
        written = build_site(resume, theme=theme, out_dir=out)
    except (UnknownTheme, BrowserMissing) as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2) from None

    for artifact in written:
        size = artifact.path.stat().st_size
        typer.echo(f"{ok}: {artifact.path} ({size / 1024:.0f} KB)")


@app.command()
def serve(
    variant: Annotated[str, typer.Option("--variant", "-v")] = "full",
    theme: Annotated[str, typer.Option("--theme", "-t")] = "classic",
    port: Annotated[int, typer.Option("--port", "-p")] = 8000,
) -> None:
    """Preview in a browser, live-reloading when resume.json or the theme changes."""
    from .serve import PortInUse, serve_preview

    try:
        target = get_variant(variant)
    except UnknownVariant as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2) from None

    try:
        serve_preview(target, theme=theme, port=port)
    except PortInUse as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2) from None


@app.command()
def check(
    path: Annotated[Path, typer.Argument(help="Resume file to check.")] = Path(
        "resume.json"
    ),
    config: Annotated[Path, typer.Option(help="Quality policy TOML.")] = Path(
        "resume-checks.toml"
    ),
    variants: Annotated[Path, typer.Option(help="Variant definitions.")] = Path(
        "variants.toml"
    ),
    fast: Annotated[bool, typer.Option(help="Skip Chromium checks.")] = False,
    strict: Annotated[bool, typer.Option(help="Fail on soft warnings too.")] = False,
    fmt: Annotated[str, typer.Option("--format", help="text or json.")] = "text",
) -> None:
    """Check CV prose, structure and published layout; never change the input."""
    import json
    from dataclasses import asdict

    from .checks import run_checks
    from .checks.config import ConfigError, load_config
    from .variants import BadHighlightPattern

    if fmt not in {"text", "json"}:
        typer.echo(f"{err}: --format must be text or json")
        raise typer.Exit(2)
    try:
        policy = load_config(config)
        resume = load_resume(path)
        cuts = load_variants(variants) if variants.exists() else {}
        violations = run_checks(resume, policy, cuts, fast=fast)
    except (
        OSError,
        ValueError,
        ValidationFailed,
        ConfigError,
        BrowserMissing,
        BadHighlightPattern,
    ) as exc:
        message = (
            "; ".join(exc.errors) if isinstance(exc, ValidationFailed) else str(exc)
        )
        typer.echo(
            json.dumps({"error": message}) if fmt == "json" else f"{err}: {message}"
        )
        raise typer.Exit(2) from None
    hard = sum(v.severity == "hard" for v in violations)
    soft = len(violations) - hard
    if fmt == "json":
        typer.echo(
            json.dumps([asdict(v) for v in violations], ensure_ascii=False, indent=2)
        )
    else:
        for rule in dict.fromkeys(v.rule for v in violations):
            typer.echo(f"{rule}:")
            for violation in violations:
                if violation.rule == rule:
                    level = "warning" if violation.severity == "soft" else "error"
                    typer.echo(f"  {level}\n{violation.render()}")
        typer.echo(f"{hard} hard violation(s), {soft} soft warning(s).")
    raise typer.Exit(1 if hard or (strict and soft) else 0)
