# Development

How to develop the toolkit and customize a CV project.

## Setup

```sh
uv sync
uv run playwright install chromium   # one-time, ~150MB
```

## Working on a CV

Run these commands from your content directory (or use `uv run --project ..`
from this checkout's `examples/`).

```sh
uv run resume serve                  # preview at localhost:8000, reloads as you edit
uv run resume build                  # -> dist/resume-{full,short}.{pdf,html,json,md}
```

`serve` is the one to use while writing or restyling: leave it running, edit
`resume.json` or `src/resume_toolkit/assets/themes/classic/style.css`, and the browser reloads itself. Add
`-v short` to preview the short cut. Reach for `build` when you want the actual PDF in `dist/`.

## Commands

| Command | Does |
|---|---|
| `uv run resume validate` | Check `resume.json` against the schema |
| `uv run resume check` | Check prose, structure and layout using `resume-checks.toml` |
| `uv run resume check --fast` | Check without Chromium; `--strict` also fails on warnings |
| `uv run resume variants` | List the variants defined in `variants.toml` |
| `uv run resume build` | Render every variant to `dist/` |
| `uv run resume build -v short -f pdf` | Render one variant, one format |
| `uv run resume site` | Every variant **plus** the `index.html` landing page — what CI publishes |
| `uv run resume serve` | Browser preview, live-reloads on edit |

To see exactly what the published site will look like, `uv run resume site` and open
`dist/index.html`.

## How it fits together

```text
resume.json ──validate (schema)──> apply variant (x-tags) ──> Jinja2 + theme ──> HTML
                                                                                  │
                                                                     Chromium print-to-PDF
                                                                                  ↓
                                                                        dist/resume-*.pdf
```

- **Content** lives in `resume.json`. Nothing else should carry CV facts.
- **Styling** lives in `src/resume_toolkit/assets/themes/classic/style.css`. The template carries structure only, so restyling
  never means touching HTML. The tokens at the top of the stylesheet (`--size-base`, `--leading`,
  `--section-gap`) are the fastest way to fit content into the page budget.
- **Cuts** live in `variants.toml`.
- **Quality policy** lives in `resume-checks.toml`; see [rule defaults and configuration](checks.md).

## Variants

One `resume.json`, several cuts of it. Tag any entry with `x-tags`:

```json
{ "name": "ACME Corp", "position": "Engineer", "x-tags": ["full"] }
```

- An entry with **no** `x-tags` is in **every** variant — so you only tag what you want to
  conditionally drop.
- A tagged entry survives only where one of its tags is in that variant's `include` list.
- `include = ["*"]` takes everything.

This works because the JSON Resume schema sets `additionalProperties: true` throughout: the tags ride
along inside a document that still validates as a standard JSON Resume and stays readable by every
other tool in the ecosystem. `x-tags` is stripped before rendering, so themes never see it.

Bullets are the one place the schema forbids that trick — `work[].highlights` items are plain
strings, so a tag can't ride inside one. The `x-highlights` extension covers it from the entry
level: a mapping from a substring of a bullet to that bullet's tags.

```json
{
  "highlights": ["Shipped X.", "Led Y."],
  "x-highlights": { "Led Y": ["full"] }
}
```

The substring must match exactly **one** bullet; the build fails loudly if an edit to the bullet
breaks the match, because a rule that silently stopped matching would silently republish the
bullet everywhere. Like `x-tags`, `x-highlights` is stripped before rendering.

## What gets published

The published JSON is not a copy of `resume.json`: it is the *variant-filtered* document — the same
entries and bullets the published PDF shows, with the variant machinery (`x-tags`, `x-highlights`)
stripped and build provenance stamped into `meta`. A parser and a reader can never disagree about
what the CV says. The same goes for the Markdown, which exists for the places styled output cannot
go: ATS web forms, plain-text email, LLM prompts.

The first published variant in `variants.toml` is the primary cut: the index
shows it first and most prominently, and the canonical `resume.json` alias and
`llms.txt` point at it. Further published variants follow it on the index as
alternatives, in file order, with the same HTML, PDF, JSON and Markdown actions.
Reorder `variants.toml` to change the primary cut.

Besides variant artifacts, the site includes `index.html`, a canonical `resume.json`
alias, `llms.txt`, `404.html`, `robots.txt` and a sitemap when `meta.canonical` is set.
The source link and build provenance come from the content repository, not the
installed toolkit. A directory without git history has no provenance stamp.

## PDF pages

The classic theme keeps every company on one page; a company taller than a
page breaks between roles, never inside one. The `page_breaks` check verifies
this on the PDF. Every PDF page carries the same footer: the variant label,
the build stamp, the canonical address (a link) and a page number. Chromium
draws it from the theme's `footer.html.j2` inside the `@page` bottom margin, so
it cannot overlap content or change pagination. The footer is a Chromium
footer template, not a CSS margin box: margin boxes would put the footer first
in the PDF text layer, glued to the page number, and could not hold a link.
The screen HTML has no page numbers and closes with a single colophon, which
print hides. A theme without `footer.html.j2` prints no footer.

## Asset packaging

Schema, templates and fonts live under `src/resume_toolkit/assets/` so uv_build
includes them in wheels and source distributions. Content paths are relative to
the working directory. For a custom theme, copy the bundled `classic` directory
to `themes/custom` in your CV project and pass `--theme custom`; local themes
are selected before bundled themes. The source checkout and installed CLI use
the same assets without reaching into another repository.

## Contributing

This repository follows [repo-standard-kit v2.0.0](https://github.com/JayTeeBat/repo-standard-kit/tree/v2.0.0),
using the `python-single` profile. See [AGENTS.md](../AGENTS.md) for the exact gate chain
and contributor responsibilities.

## Why these choices

- **Chromium, not WeasyPrint.** WeasyPrint needs MSYS2 + Pango installed by hand on Windows, which
  breaks clone-and-go. Playwright vendors its own browser.
- **Fonts are bundled** (`src/resume_toolkit/assets/themes/classic/fonts/`, Source Sans 3, OFL). Relying on system fonts means
  different metrics — and so different pagination — between a local Windows build and Linux CI.
- **The schema is vendored and pinned** (`src/resume_toolkit/assets/schema/`), so validation is hermetic and offline. See
  [`schema/SOURCE.md`](../src/resume_toolkit/assets/schema/SOURCE.md) for provenance and how to refresh it.
- **Format checking is on.** The schema declares `format` on 11 fields (`email` and 10 `uri`s), which
  `jsonschema` ignores unless asked; those are exactly the fields where a typo is invisible on the
  page but costly in life.

## CI

Pushes to `main` and pull requests run the standard gate chain with Chromium
installed for slow tests. Compliance runs independently on pull requests.
The toolkit does not deploy a site; see [getting started](getting-started.md)
for a publishing workflow in your content repository.

## Tests

```sh
uv run pytest              # all
uv run pytest -m 'not slow'   # skip the ones that drive a real browser
```

## Pre-commit

```sh
uv run pre-commit install
```

The standard hooks check formatting, lint, types, Markdown, file hygiene,
secrets and repository compliance. Example CLI tests cover content checks;
there is no repository-root CV hook. Run `uv run pre-commit run --all-files`
to check the whole repository.
