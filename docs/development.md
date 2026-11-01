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
uv run resume build                  # render every variant to dist/
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
| `uv run resume site` | Every published variant **plus** the `index.html` landing page — what CI publishes |
| `uv run resume serve` | Browser preview, live-reloads on edit |

To see exactly what the published site will look like, `uv run resume site` and open
`dist/index.html`.

## How it fits together

```text
resume.json ──validate (schema)──> apply variant (x-tags) ──> Jinja2 + theme ──> HTML
                                                                                  │
                                                                     Chromium print-to-PDF
                                                                                  ↓
                                                                        dist/<Name>-Resume*.pdf
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

### Per-variant design tokens

A variant may override tokens declared by the selected theme:

```toml
[one-page]
include = []
publish = true
style = { "--size-base" = "9pt", "--leading" = "1.2", "--section-gap" = "6pt" }
```

The renderer appends these custom properties after the theme stylesheet, in
both HTML and the separate PDF footer document. Builds, previews and Chromium
checks use the same overrides; other variants keep the theme defaults. JSON
and Markdown are unaffected. Unknown variant keys, incorrect types, non-custom
property names, unknown theme tokens and unsafe values fail with a configuration
error. Values must be nonempty strings without `;`, `{`, `}`, `<`, backslashes,
CSS comments or control characters. Unknown tokens are checked when rendering
against the selected theme. This validates the declaration boundary, not every
CSS value grammar; inspect the computed layout after changing tokens.

The classic theme exposes body size, leading, section and entry gaps, heading
gap/padding, role and summary gaps, highlights and bullet gaps, skills row gap,
and company, title, meta and footer sizes. Defaults live in `style.css`.
Page margins remain fixed at 15 mm vertically and 14 mm horizontally; variant
style cannot change them. Thus `print_content_width` and `print_content_height`
keep their existing meaning. Custom themes own their geometry and check policy.

For compact cuts, keep body text at least **9pt**, dates/meta/footer at least
**7.5pt**, body line-height at least **1.2**, and side margins at least **12 mm**.
Keep the 15 mm bottom margin for the running footer. These are authoring floors,
not automatic checks. The footer defaults to 7.5pt; leave `--size-footer` unset
so every cut prints the same footer. Leave at least one body line spare,
measure the PDF, and review the rendered result.

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
Reorder `variants.toml` to change the primary cut. Its PDF footer and HTML/Markdown
colophons omit the version label; every other cut keeps it. This applies to both
`resume build` and `resume site`. With no published variant, all labels remain.

Besides variant artifacts, the site includes `index.html`, a canonical `resume.json`
alias, `llms.txt`, `404.html`, `robots.txt` and a sitemap when `meta.canonical` is set.
The source link and build provenance come from the content repository, not the
installed toolkit. A directory without git history has no provenance stamp.
Readers see the stamp as `2026-10-31 · rev 39140c4` in the PDF footer, the
screen colophon and the Markdown colophon; machines read `meta.version` as
CalVer with the hash as SemVer build metadata, `2026.10.31+39140c4`. A build
with uncommitted edits to `resume.json` is dated today and reads
`2026-10-31 · rev 39140c4 (modified)` and `2026.10.31+39140c4.dirty`.

PDF filenames identify the person: `<Name>-Resume.pdf` for the primary cut,
`<Name>-Resume-<Variant>.pdf` for every other cut (including private builds).
`Name` comes from `basics.name`: ASCII-fold accents, join whitespace-separated
words with `-`, then drop characters outside `[A-Za-z0-9-]`. An empty result
fails the build. Variant parts are title-cased (`one-page` becomes `One-Page`).
`resume build -v` uses the same primary cut as the site; with no published
variants, every PDF includes its variant suffix. HTML, JSON and Markdown keep
`resume-<variant>.*`, and `/resume.json` remains the primary JSON alias.
Old PDF URLs have no redirects. The sitemap continues to list HTML pages only.

The classic HTML title and PDF Title are `<basics.name> — Resume`. PDF Author
is `basics.name`, Subject is `basics.label`, and Keywords are the filtered cut's
skill keywords, deduplicated in original order and separated by commas.
Post-processing with pypdf preserves Chromium's title, dates and page content;
it adds no timestamps, generated IDs or hidden body text. Custom themes retain
their own HTML title as the PDF Title.

## PDF pages

The classic theme keeps every company on one page; a company taller than a
page breaks between roles, never inside one. The `page_breaks` check verifies
this on the PDF. Every PDF page carries the same footer, on one line across
the page width: fields at equal gaps from margin to margin, a `·` centred
in each gap, the variant label (`One-Page Version`) for non-primary cuts, the build stamp
(`2026-10-31 · rev 39140c4`), the canonical address (a link) and the page
number (`1 / 2`). The screen HTML closes with the same row, same type and
colour, minus the page number. Chromium
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
