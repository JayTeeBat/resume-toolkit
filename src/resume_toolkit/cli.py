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
        raise typer.Exit(2)
    except ValidationFailed as exc:
        typer.echo(f"{err}: {path.name} does not satisfy the JSON Resume schema\n")
        for problem in exc.errors:
            # ASCII deliberately: a Windows cp1252 console mangles "·" to "?".
            typer.echo(f"  - {problem}")
        typer.echo(f"\n{len(exc.errors)} violation(s).")
        raise typer.Exit(1)


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
        tags = "everything" if variant.includes_everything else (
            ", ".join(sorted(variant.include)) or "untagged entries only"
        )
        name = typer.style(variant.name, bold=True)
        typer.echo(f"{name}\n    {variant.description}\n    includes: {tags}")


@app.command()
def build(
    variant: Annotated[
        str | None,
        typer.Option("--variant", "-v", help="Variant to build. Default: all of them."),
    ] = None,
    theme: Annotated[str, typer.Option("--theme", "-t", help="Theme directory name.")] = "classic",
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="pdf, html, json, md, or all."),
    ] = "all",
    out: Annotated[Path, typer.Option("--out", "-o", help="Output directory.")] = DIST_DIR,
) -> None:
    """Render resume.json to dist/."""
    if fmt not in {"pdf", "html", "json", "md", "all"}:
        typer.echo(f"{err}: --format must be pdf, html, json, md or all (got {fmt!r})")
        raise typer.Exit(2)
    formats = ("pdf", "html", "json", "md") if fmt == "all" else (fmt,)

    resume = _load_or_exit()

    try:
        targets = [get_variant(variant)] if variant else list(load_variants().values())
    except UnknownVariant as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2)

    if not targets:
        typer.echo(f"{err}: variants.toml defines no variants")
        raise typer.Exit(2)

    try:
        for target in targets:
            for artifact in build_variant(
                resume, target, theme=theme, formats=formats, out_dir=out
            ):
                size = artifact.path.stat().st_size
                typer.echo(f"{ok}: {artifact.path} ({size / 1024:.0f} KB)")
    except (UnknownTheme, BrowserMissing) as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2)


@app.command()
def site(
    theme: Annotated[str, typer.Option("--theme", "-t", help="Theme directory name.")] = "classic",
    out: Annotated[Path, typer.Option("--out", "-o", help="Output directory.")] = DIST_DIR,
) -> None:
    # ASCII deliberately, as in _load_or_exit: a Windows cp1252 console mangles
    # "-" typed as an em-dash into "?" when typer prints this help text.
    """Build every variant plus an index.html - what CI publishes to Pages."""
    resume = _load_or_exit()

    try:
        written = build_site(resume, theme=theme, out_dir=out)
    except (UnknownTheme, BrowserMissing) as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2)

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
        raise typer.Exit(2)

    try:
        serve_preview(target, theme=theme, port=port)
    except PortInUse as exc:
        typer.echo(f"{err}: {exc}")
        raise typer.Exit(2)
