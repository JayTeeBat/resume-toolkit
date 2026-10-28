# ADR 0003: Gates as a config-driven command

## Status

Accepted for this refactor.

## Context

The quality gates mixed reusable rules with CV facts and editorial decisions
inside pytest tests. Extracting the toolkit later would carry that coupling
into another repository. Content changes also changed toolkit test behavior.

## Decision

Move each rule into `resume_toolkit.checks`, returning structured violations
with location, offending text, suggested edit, rule and hard/soft severity.
Keep linguistic data in the package and CV policy in `resume-checks.toml`.
Expose `resume check`, with fast, strict and JSON modes. Preserve the failure
message contract and prohibit auto-fixing. See [configuration](../checks.md)
for rule mappings and defaults.

Replace owner-data tests with fictional fixtures and direct rule tests.
Run the full command on real content in CI, and its fast mode in pre-commit.
Keep schema validation and the existing rendering and publishing interfaces.

## Consequences

The tool owns rules; the CV repository owns facts and editorial policy.
This is the first step toward extraction, not a repository split. Codespell
and PDF inspection become runtime dependencies. Codespell retains its original
repository-wide scope and project skip settings; spelling exceptions move into
the quality policy. Invalid dates produce diagnostics rather than crashing the
career-gap check. Missing Chromium fails the command instead of skipping a gate.

Full checks require browser installation. English linguistic heuristics remain
explicitly limited to their curated lists. Timeline comparisons retain month
precision. Existing owner warnings are preserved rather than suppressed.
