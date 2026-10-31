# ADR 0005: Company-aware pagination and a running PDF footer

## Status

Accepted for 0.2.0.

## Context

A printed CV is read page by page. A company split across pages hides its
tenure from the roles on the next page, and a PDF page separated from the
others cannot say which cut, build or page it is. The colophon closed only the
last page. Content repositories also publish more than one cut, each with its
own page budget, while variant rules checked a single `published_variant`.

## Decision

Keep company blocks whole with `break-inside: avoid`; roles were already kept
whole. Verify the result on the printed PDF with a `page_breaks` rule that pins
invisible link annotations to block edges and reads back their pages, instead
of predicting pagination from screen layout.

Draw the footer with a Chromium footer template rendered from the theme's
`footer.html.j2`, inside the existing `@page` bottom margin. CSS margin boxes
(`@bottom-left`, `counter(page)`) were rejected: Chromium writes them first in
the PDF text layer, glued to the page number, and their `content` cannot hold
a link. The template keeps the footer last in reading order, once per page,
with the canonical address clickable on every page, and leaves the content
area and so the pagination unchanged. Print hides the in-flow colophon, so its
text appears once per page.

The footer is one line of four fields spread at equal gaps across the page
width, a separator dot centred in each gap: variant label, build stamp,
canonical address, page number. The screen colophon is the same row minus the
page number (one shared macro and `.footer-row` class). The separators are
real text, so the PDF text layer reads
`One-Page Version · 2026-10-31 · rev 39140c4 · latest at example.com/cv · 1 / 2`,
the same layout, wording and 7.5pt size on every cut; only the variant label
and the page count differ. The stamp shown to readers is `Stamp.label`
(`YYYY-MM-DD · rev <7-char hash>`, with `(modified)` appended for uncommitted edits);
the machine-readable `meta.version` stays CalVer with the hash as SemVer build
metadata (`2026.10.31+39140c4`, `+39140c4.dirty`).

Check every published cut by default, with per-variant page budgets and
per-variant rule exemptions. Replace `published_variant` with
`published_variants`; the old key fails with a migration hint.

## Consequences

Themes that want the footer ship `footer.html.j2`; without it a PDF has none.
The footer template carries its own copy of the stylesheet and fonts. Printing
the HTML from a browser shows no colophon. Variant rules launch Chromium once
per checked cut, so full checks take longer as cuts are added. Content
repositories using `published_variant` must rename it.
