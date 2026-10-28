# AGENTS.md

## Repository Purpose

Validate and render a JSON Resume as HTML, PDF, JSON, Markdown,
and a GitHub Pages site.

## Repository Context

- Repository name: `my-resume`; Python package: `resume-toolkit`
- Primary language(s): `Python`
- Runtime/build system: `uv` with `uv_build` in `pyproject.toml`
- Repository type: CV-as-code CLI and static site
- Standards source: [repo-standard-kit] — quality gates derive from its
  [quality-gates spec][quality-gates]; review this repository against it
  periodically for standards drift
- Key directories:
  - `src/`: production package code
  - `tests/`: automated tests
  - `docs/`: durable repository knowledge

## Human And Agent Responsibilities

### Goal

Define clear decision boundaries between humans and agents so implementation
work can move quickly without ambiguity or accidental overreach.

### Human Responsibilities

Humans own:

- product scope and intent
- security exceptions and secret handling
- merge and release authority
- production access and production operations sign-off
- approval of breaking API, schema, or migration changes
- architectural exceptions to the documented standard

### Agent Responsibilities

Agents own:

- implementation within documented repository boundaries
- tests, regression coverage, and local verification
- documentation updates tied to behavior changes
- CV rendering templates and development tooling maintenance
- surfacing risks, missing decisions, and unclear contracts

### Shared Expectations

- Keep code, tests, and docs aligned
- Prefer small, reviewable changes
- Make operational boundaries explicit
- Do not rely on undocumented local knowledge

### Agent Prohibitions

Agents must not:

- bypass documented quality gates
- weaken typing or test expectations without explicit instruction
- make security, release, or breaking-change decisions alone
- modify out-of-scope systems without explicit approval

## Agent Operating Mode

Agent behaviour in this repository is calibrated, not left to model defaults.
Each dial runs from 1 to 5, where 5 is the maximum:

- **Verbosity:** 2 / 5
- **Precision, repeatability, determinism:** 4 / 5

Low verbosity means:

- Answer what was asked; do not restate the request or read the plan back
- Report outcomes, not a narration of the steps taken to reach them
- Prefer a diff, a command, or a `path:line` reference over prose describing it
- Open with the result; no preamble, and no recap the transcript already shows
- Spend words on decisions the reader must make, on risks, and on failures

High precision, repeatability, and determinism mean:

- Verify against the repository before asserting, and cite `path:line`
- Reuse the pattern already in the file rather than introducing a second one
- Make the smallest change that satisfies the requirement, and nothing beyond it
- Run the documented quality gates in order and report their real output
- Pin versions, ordering, and formatting rather than leaving them to chance
- State assumptions explicitly where the repository does not settle a choice
- The same task on the same input should reach the same result on a second run

The levels are policy values, not prose: `repo-check` reports drift from them
and `repo-adopt` restores them.

## Single Source Of Truth

`resume.json` is the only home for CV facts. Never invent CV facts; ask the owner
when dates, claims, or wording need factual confirmation. `variants.toml` selects
cuts, and templates must not duplicate personal content.

Anything stated twice drifts, and the copy that drifts is the one nobody is
reading when it matters. Before writing, look for what already exists and
derive from it.

- **One home per fact.** A value, a command, a version, a path, a section
  order, a schema: declared in exactly one place, with every other use reading
  from that place
- **Derive, do not copy.** Where two artefacts must agree, generate one from
  the other or both from a shared source, and put the check that they still
  agree in the quality gates
- **Reference, do not restate.** Link to the document that owns a subject
  instead of summarising it somewhere it will go stale
- **Extend rather than parallel.** A second helper, constant, fixture, config
  key, or type that means what an existing one means is duplication even when
  the wording differs — change the original instead
- **Make unavoidable duplication fail loudly.** Where a copy cannot be removed,
  add a test or check that regenerates it and compares, so drift is a failure
  rather than a surprise
- **Deleting the stale copy is part of the change** that made it stale, not a
  follow-up

This applies to code, configuration, documentation, fixtures, and data alike.
When a change means editing the same fact in more than one file, treat that as
the defect to fix first.

## Workflow

### Default Model

Use trunk-based development with pull requests.

### Branching Rules

- `main` is the primary long-lived integration branch and is always releasable
- work happens on short-lived branches
- use one branch per objective
- branch prefixes:
  - `feat/`
  - `fix/`
  - `refactor/`
  - `docs/`
  - `chore/`

### Parallel Collaboration

- prefer small PRs over long-lived branches
- use stacked PRs when a larger change needs sequencing
- rebase private branches frequently to reduce drift
- avoid multiple concurrent branches changing the same subsystem without
  coordination

### History Rules

- rebasing private branches is allowed
- rewriting shared branches is not allowed
- merge through reviewed PRs only
- cut releases from `main` with tags

## Quality Gates

Install Chromium once with `uv run playwright install chromium`.
Build all published outputs with `uv run resume site`; preview edits with
`uv run resume serve` (or `-v short`). Validate data with `uv run resume validate`.
Run `uv run resume check` for full CV quality gates (`--fast` skips Chromium).

Run from repo root:

1. `uv sync --locked`
2. `uv run pre-commit run --all-files`
3. `uv run pytest`
4. `uv build`

The quality job's effective permissions must be exactly `contents: read`, and
every remote action or reusable workflow must be pinned to a full 40-character
commit SHA. Keep version comments and GitHub Actions Dependabot configuration
so those pins remain maintainable.

Branch protection must require the separate `quality` and `compliance` status
checks. Quality executes the gate chain; compliance independently checks the
repository against the standard. Keep these canonical names so the same
ruleset applies to every adopting repository.

## Coding Standards

- Type all production function signatures
- Minimize `Any` and justify it when required
- Keep I/O boundaries explicit
- Separate side effects from business logic
- Separate durable logic from scripts
- Preserve public interface stability by default

## Testing Policy

- `resume check` enforces CV gates from `resume-checks.toml`; tests use fictional fixtures
- Run the full suite, including Chromium page-budget and contact-header tests
- Logic changes require unit tests
- Boundary changes require integration tests
- Bug fixes require regression tests

## Documentation Rules

- Update `README.md` when setup or usage changes
- Update `AGENTS.md` when operating rules change
- Add ADRs for significant architecture decisions
- Keep the `repo-standard-kit` reference in `README.md` and `AGENTS.md`
  current, and check this repository against it periodically

## Repository Layout

- `src/`: production package code
- `tests/`: automated tests
- `docs/`: durable project knowledge
- `resume.json`: all CV facts
- `variants.toml`: variant selection and publishing configuration
- `resume-checks.toml`: CV quality policy; defaults in [docs/checks.md](docs/checks.md)
- `schema/`: pinned JSON Resume schema
- `themes/classic/`: rendering templates, CSS, and bundled fonts
- `site/`: landing-page template
- `dist/`: generated outputs; never commit

## Change Control Notes

Preserve schema validation, variant semantics, output formats, and public CLI
commands. Keep the full-history checkout: the colophon dates content from git.
Only `main` deploys Pages; all branches upload preview artifacts. Open PRs against
`main`, or explicitly name and link the parent PR when stacking. Never merge
without owner authorization. Changes to CV facts require owner confirmation.
The MIT grant excludes CV content and its derived outputs; see [LICENSE](LICENSE).

[repo-standard-kit]: https://github.com/JayTeeBat/repo-standard-kit/tree/v2.0.0
[quality-gates]: https://github.com/JayTeeBat/repo-standard-kit/blob/v2.0.0/docs/quality-gates.md
