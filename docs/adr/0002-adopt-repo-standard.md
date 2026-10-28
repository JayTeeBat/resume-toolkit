# ADR 0002: Adopt repo-standard-kit v2.0.0

## Status

Accepted; updated for toolkit extraction.

## Context

The rendering toolkit needs shared formatting, typing, file hygiene and CI contracts.

## Decision

Adopt [repo-standard-kit v2.0.0](https://github.com/JayTeeBat/repo-standard-kit/tree/v2.0.0),
profile `python-single`, standard major `2`. Use the pinned direct uvx checker
with `--strict`. Keep independent `quality` and `compliance` checks and full SHA
pins for remote actions.

## Consequences

Keep uv_build, the full Chromium suite and fixture-based testing. The quality
chain adds browser installation; content repositories own Pages deployment.
Use a local compliance hook invoking the pinned uvx command. Standard hooks
retain their required entries and arguments. The empty secrets baseline records
an audit, without suppressing the detect-secrets hook.
