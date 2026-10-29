# Use it for your own CV

## Create a content project

Initialize a uv project and install the toolkit from the tag as shown in the
[README](../README.md#install). Copy the three files in [examples](../examples)
into your project root: `resume.json`, `variants.toml` and `resume-checks.toml`.
Replace the fictional JSON Resume with your own facts. Set `meta.canonical` to
your Pages URL and mark public variants with `publish = true`. The first
published variant is the primary cut on the site; see
[development](development.md#what-gets-published).

The checks file can be empty to use defaults. Add only overrides you need;
[checks](checks.md) documents every rule. Keep private variants unpublished.

## Build and preview

```sh
uv run resume validate
uv run resume check --fast
uv run playwright install chromium
uv run resume check
uv run resume build
uv run resume site
uv run resume serve
```

`dist/` holds generated outputs. Keep it out of git. Commit your content so
build stamps can identify its revision. See [development](development.md#variants)
for tags and per-highlight selection.

## Publish with GitHub Pages

Select **GitHub Actions** as the Pages source in your content repository's
settings. Add a workflow like this there; the toolkit repository has no deploy job.
Keep action pins updated with Dependabot.

```yaml
name: Publish CV
on:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3
      - run: uv sync --locked
      - run: uv run playwright install --with-deps chromium
      - run: uv run resume validate
      - run: uv run resume check
      - run: uv run resume site
      - uses: actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9 # v5.0.0
        with:
          path: dist/
  deploy:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1
```
