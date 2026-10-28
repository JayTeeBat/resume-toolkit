# Resume Toolkit

## Overview

Turn a JSON Resume into styled HTML, PDF, JSON, Markdown and a static Pages site.
Define variants with tags and check prose, chronology and layout with configurable rules.
Bundled fonts, an offline schema and fictional fixtures make the toolkit portable and testable.

## Install

Requires Python 3.13+ and uv. Once the repository and tag are published:

```sh
uv add "resume-toolkit @ git+https://github.com/JayTeeBat/resume-toolkit@v0.1.0"
uv run playwright install chromium
```

For a standalone CLI:

```sh
uv tool install "resume-toolkit @ git+https://github.com/JayTeeBat/resume-toolkit@v0.1.0"
uv tool run --from "resume-toolkit @ git+https://github.com/JayTeeBat/resume-toolkit@v0.1.0" playwright install chromium
```

No PyPI release is planned yet.

## Usage

Try the complete fictional example from a local checkout:

```sh
uv sync --locked
uv run playwright install chromium
cd examples
uv run --project .. resume validate
uv run --project .. resume check --fast
uv run --project .. resume build
uv run --project .. resume site
```

Outputs go to `examples/dist/`. Commands read content from the working directory:
`validate`, `check`, `variants`, `build`, `site` and `serve`.
Use `resume build -v short -f pdf` for one output or `resume serve` for live preview.
See [getting started](docs/getting-started.md), [checks](docs/checks.md) and
[development](docs/development.md) for configuration and design details.

## Development

```sh
uv sync --locked
uv run playwright install chromium
uv run pre-commit install
uv run pre-commit run --all-files
uv run pytest
uv build
```

This repository follows [repo-standard-kit v2.0.0](https://github.com/JayTeeBat/repo-standard-kit/tree/v2.0.0),
profile `python-single`, standard major `2`. The mandatory gates derive from its
[quality-gates specification](https://github.com/JayTeeBat/repo-standard-kit/blob/v2.0.0/docs/quality-gates.md).
See [AGENTS.md](AGENTS.md) for contributor responsibilities.

## License

[MIT](LICENSE). Bundled Source Sans 3 fonts retain their
[OFL license](src/resume_toolkit/assets/themes/classic/fonts/LICENSE.md).
