# ADR 0004: Extract the toolkit from my-resume

## Status

Accepted for local preparation; publication is a separate step.

## Context

A reusable renderer and quality checker should be independently installable,
testable and reviewable as a portfolio project. Personal content has a separate
lifecycle, history and publishing URL.

## Decision

Extract toolkit paths with git-filter-repo, preserving their history while
excluding root CV data and its README from every retained commit. Audit retained
history separately; do not silently remove historical identifiers. Keep content
and publishing in the original repository, preserving its URL and history.

Release version 0.1.0 under MIT, with bundled font licenses retained. Install
from a git tag; defer PyPI publication until there is a reason to support it.
Package rendering assets beside the Python code so installed builds work without
the source checkout. Resolve content from the current working directory.

## Consequences

The toolkit owns rules, rendering and fictional examples. Content repositories
own facts, policy and site deployment. Root asset directories move beneath the
package in a new commit so wheels contain them without duplicate source copies.
Local themes remain customizable. New releases require consumer tag updates.
