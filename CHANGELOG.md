# Changelog

## [Unreleased]

Planned for 0.3.0.

### Changed

- Breaking: PDF downloads carry the ASCII-folded name from `basics.name`:
  `<Name>-Resume.pdf` for the first published cut, `<Name>-Resume-<Variant>.pdf`
  for others. Old PDF URLs have no redirects. Other formats keep their names.
- PDF metadata includes the author, subject and ordered, deduplicated skill
  keywords from the filtered cut. The classic HTML title and PDF Title use
  `<name> — Resume`; page content and pagination are unchanged.

## 0.2.1 - 2026-10-31

### Changed

- Landing-page cards show the version name and its four actions only; variant
  descriptions no longer appear there. They remain in `llms.txt` and
  `resume variants`.
- The landing-page footer shows only the update date (`Updated 2026-10-31`);
  the "Built from resume.json" source link is gone.

## 0.2.0 - 2026-10-31

### Added

- Fast, hard `required_sections` and `role_highlights` rules enforce configured
  content coverage after variant filtering, including required source roles.
- Standards register with a pin-drift test.

- Per-variant `style` tables override declared theme design tokens in HTML,
  PDF, preview and layout checks, with configuration validation and documented
  readability floors. Classic spacing and small-text tokens preserve defaults.

- Running PDF footer on every page, one line of four fields spread at equal
  gaps across the page with a dot centred in each gap: variant label, build
  stamp, clickable canonical address and page number. The screen colophon is
  the same row without the page number, in the same pale grey (the footer
  template forces exact print colour so Chromium no longer darkens it), from the theme's `footer.html.j2` (ADR 0005). The footer
  is 7.5pt by default and identical on every cut.
- `Stamp.label`, the human-readable build stamp (`2026-10-31 · rev 39140c4`,
  `… (modified)` for uncommitted edits), shown in the PDF footer and the
  screen and Markdown colophons.
- `page_breaks` check: no PDF page break inside a role, nor inside a company
  block that fits on one page; read back from the printed PDF.
- Per-variant `page_budget` table, `published_variants` and
  `variant_exemptions` check configuration; `print_content_height`.
- Landing page leads with the primary (first published) cut and lists further
  published cuts as alternatives with the same four actions.

### Changed

- `unit_spacing` cites the SI Brochure, 9th edition (2019), §5.4.3 and §5.4.7,
  and groups its symbols as SI, accepted for use with the SI, and common
  non-SI battery units. `Nm` is no longer a recognised symbol: SI writes
  `N m` or `N·m`.
- Breaking: `published_variant` is replaced by `published_variants`; variant
  rules (`quantified`, `page_budget`, `header`, `page_breaks`) check every
  published cut by default.
- The classic theme keeps each company on one page and breaks between roles
  only when a company is taller than a page.
- Profile links print their address (`linkedin.com/in/…`) in HTML and Markdown,
  and the skills section is headed "Skills".
- Contact separators are tighter (7pt) so full profile addresses keep the
  header on one line.
- The screen colophon is hidden in print, where the running footer replaces it.
- Build versions drop git's `g` prefix and mark uncommitted edits as build
  metadata: `2026.10.31+39140c4` and `2026.10.31+39140c4.dirty` (was
  `+g39140c4` and `+g39140c4-dirty`). The colophons show `Stamp.label`
  instead of the version.
- Classic `--size-footer` default is 7.5pt (was 7.2pt).

## 0.1.0

- Extract the reusable toolkit with its development history.
- Validate JSON Resume and render HTML, PDF, JSON, Markdown and static sites.
- Select variants with tags and check content with configurable rules.
- Bundle offline schema, templates and OFL fonts for installation from a git tag.
- Add fictional examples, CLI integration tests and toolkit documentation.
- Adopt repo-standard-kit v2.0.0 quality and compliance workflows.
