# Changelog

## [Unreleased]

## 0.2.0 - unreleased

### Added

- Fast, hard `required_sections` and `role_highlights` rules enforce configured
  content coverage after variant filtering, including required source roles.
- Standards register with a pin-drift test.

- Per-variant `style` tables override declared theme design tokens in HTML,
  PDF, preview and layout checks, with configuration validation and documented
  readability floors. Classic spacing and small-text tokens preserve defaults.

- Running PDF footer on every page: variant label, build stamp, clickable
  canonical address and a page number, from the theme's `footer.html.j2`
  (ADR 0005).
- `page_breaks` check: no PDF page break inside a role, nor inside a company
  block that fits on one page; read back from the printed PDF.
- Per-variant `page_budget` table, `published_variants` and
  `variant_exemptions` check configuration; `print_content_height`.
- Landing page leads with the primary (first published) cut and lists further
  published cuts as alternatives with the same four actions.

### Changed

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

## 0.1.0

- Extract the reusable toolkit with its development history.
- Validate JSON Resume and render HTML, PDF, JSON, Markdown and static sites.
- Select variants with tags and check content with configurable rules.
- Bundle offline schema, templates and OFL fonts for installation from a git tag.
- Add fictional examples, CLI integration tests and toolkit documentation.
- Adopt repo-standard-kit v2.0.0 quality and compliance workflows.
