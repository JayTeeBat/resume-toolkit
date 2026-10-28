# ADR 0002: Adopt repo-standard-kit v2.0.0

## Status

Accepted for this adoption.

## Context

The CV toolchain already validates data and exercises Chromium rendering, but
lacks a shared contract for formatting, typing, file hygiene, and compliance.

## Decision

Adopt [repo-standard-kit v2.0.0](https://github.com/JayTeeBat/repo-standard-kit/tree/v2.0.0)
with the `python-single` profile and standard major `2`. Pin checker invocations
to this release so upstream changes cannot silently select a newer policy.
Use the documented direct `uvx` compliance workflow with `--strict`, retaining
the canonical `quality` and `compliance` check names. Release-tag immutability
is assumed as permitted by the kit; remote Actions use full commit SHAs.

## Consequences

Keep the existing uv_build backend, full Chromium suite, local resume-gates,
full-history content stamps, artifact uploads, and main-only Pages deploy.
The quality job has only contents read permission; Pages write permissions
remain confined to deploy. Keep the existing action major versions to limit
migration scope. Enable recommended PT rules and the 88-column baseline.
Type-check both src and tests; no policy exemptions are needed.

The code is MIT licensed, while CV facts and all derived outputs remain
reserved. Existing README content stays available under the standard headings.
Branch protection must eventually require quality and compliance in place of
build; repository settings are managed separately from this stacked PR.

The generated secrets baseline contains no candidates. RSK007 requires the
exact detect-secrets invocation and rejects baseline arguments, so the hook
scans without suppressions; the empty baseline records the adoption audit.
