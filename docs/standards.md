# Standards register

| Standard | Version / pin | Scope (what it governs here) | Enforcement (rule / workflow / test, or "not enforced") | Decision (ADR link, if any) |
|---|---|---|---|---|
| JSON Resume / JSON Schema | `d8ebc8c816ae15db10f40e0fefaf4c935e025ea1`, draft-07 | Offline vendored schema; provenance in `assets/schema/SOURCE.md` within the package | `resume validate`, `test_validate.py`, `test_standards.py` | [Extraction](adr/0004-extract-toolkit.md) |
| ISO 8601 | `YYYY-MM` default | CV dates, month precision | `dates`, `date_format`; format checks, not full calendar validation | [Checks](adr/0003-gates-as-config-driven-command.md) |
| BIPM SI Brochure | SI unit spacing convention | Whitespace between numbers and supported unit symbols | `unit_spacing`; curated symbols only | — |
| schema.org Person / OpenGraph | Unversioned vocabularies | Landing-page structured data and preview metadata | `site.py`, `test_site.py`; no external conformance validator | — |
| Sitemaps protocol | 0.9 | Canonical site URLs | `site.py`, `test_site.py` | — |
| llms.txt | Unversioned proposal | Primary CV and alternative links | `llms.txt.j2`, `test_site.py`; no external conformance validator | — |
| repo-standard-kit | v2.0.0, `python-single` | Repository quality and compliance | `compliance.yml`, pre-commit, `test_standards.py` | [Adoption](adr/0002-adopt-repo-standard.md) |

## Deliberate deviations

- No PyPI publication; install from git tags: [ADR 0004](adr/0004-extract-toolkit.md).
