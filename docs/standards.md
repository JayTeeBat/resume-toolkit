# Standards register

| Standard | Version / pin | Scope (what it governs here) | Enforcement (rule / workflow / test, or "not enforced") | Decision (ADR link, if any) |
|---|---|---|---|---|
| JSON Resume / JSON Schema | `d8ebc8c816ae15db10f40e0fefaf4c935e025ea1`, draft-07 | Offline vendored schema; provenance in `assets/schema/SOURCE.md` within the package | `resume validate`, `test_validate.py`, `test_standards.py` | [Extraction](adr/0004-extract-toolkit.md) |
| ISO 8601 | `YYYY-MM` default | CV dates, month precision | `dates`, `date_format`; format checks, not full calendar validation | [Checks](adr/0003-gates-as-config-driven-command.md) |
| [BIPM SI Brochure](https://www.bipm.org/en/publications/si-brochure) | SI Brochure, 9th edition (2019); §5.4.3 (number–unit space), §5.4.7 (`%`) | Whitespace between a number and a listed unit symbol | `unit_spacing` (curated symbol list in `checks/language.py`), `test_standards.py` | — |
| schema.org Person / OpenGraph | Unversioned vocabularies | Landing-page structured data and preview metadata | `site.py`, `test_site.py`; no external conformance validator | — |
| Sitemaps protocol | 0.9 | Canonical site URLs | `site.py`, `test_site.py` | — |
| llms.txt | Unversioned proposal | Primary CV and alternative links | `llms.txt.j2`, `test_site.py`; no external conformance validator | — |
| repo-standard-kit | v2.0.0 (`417aa92f1711fe8266622ef9dde797e0f40f2def`), `python-single` | Repository quality and compliance | `compliance.yml`, pre-commit, `test_standards.py` | [Adoption](adr/0002-adopt-repo-standard.md) |

## Deliberate deviations

- `unit_spacing` also spaces common non-SI battery units (`Ah`, `kWh`, `rpm`, `bar`) by the same convention; it checks spacing only, not whether a unit is SI.
- No PyPI publication; install from git tags: [ADR 0004](adr/0004-extract-toolkit.md).
