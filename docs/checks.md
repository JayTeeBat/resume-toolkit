# CV quality checks

`uv run resume check` reads `resume.json`, `variants.toml` and `resume-checks.toml`
from the working directory. Override them with a positional resume path,
`--variants PATH` and `--config PATH`. A missing policy uses defaults; a missing
variants file means the whole document is checked. Unknown keys, rule names,
wrong types and inconsistent limits are configuration errors.

`--fast` skips only the Chromium rules: `page_budget`, `header` and `page_breaks`. `--strict` makes soft warnings
fail too. `--format json` returns an array with `where`, `text`, `fix`, `rule`
and `severity` for each violation; input/infrastructure errors return an `error`
object. Exit codes are 0 for success, 1 for hard violations (or strict warnings),
and 2 for invalid inputs or unavailable dependencies. No command auto-fixes prose.

## Rules and defaults

All rules below are enabled by default. `enabled = ["punctuation", "dates"]`,
for example, selects only those two. Every violation is hard except length
advice within the hard bounds. Minimal policy: an empty TOML file.

| Rule | Config key(s) and default behavior |
|---|---|
| `punctuation` | Sentence fields end with a period; no additional settings |
| `spelling` | `spelling = "none"`; `"en-GB"` selects built-in US spelling stems |
| `proper_names` | `proper_names = {}`; mapping from incorrect to correct casing |
| `typography` | No double/edge spaces, spaced hyphens, ASCII multiplication or trailing currency symbols |
| `unit_spacing` | Built-in unit symbols require whitespace after numbers (`10 kWh`, `±3 %`, `25 °C`), per the [SI Brochure, 9th edition (2019)](https://www.bipm.org/en/publications/si-brochure) §5.4.3 and §5.4.7; the list in `checks/language.py` is SI, accepted-for-use and common battery units, curated rather than exhaustive |
| `tense` | Built-in English verb lists; current role present, ended role past |
| `verb_led` | Highlights start with a recognized present/past verb or an `-ed` word |
| `quantified` | At least one digit in each published work entry's summary/highlights |
| `lengths` | `summary_sentences = 1`, `summary_soft_max = 25`, `summary_hard_max = 30`; minimum 1 word |
| `lengths` | `highlight_soft_range = [10, 30]`, `highlight_hard_range = [3, 40]`; whitespace-separated words |
| `required_sections` | `required_sections = {}`; required non-empty sections after filtering, wildcard plus variant union |
| `role_highlights` | `role_highlights = {}`; per-variant minimum nonblank work highlights, optionally since a month |
| `highlights` | Each work entry has at least one nonblank highlight |
| `locations` | `location_pattern = '[^,\s][^,]*, [^,\s][^,]*'`; full match for City, Country |
| `tags` | Tags name variants or their included tags; `*` is a selector, never a tag |
| `chronology` | Work entries ordered by descending start month |
| `overlaps` | Work spans do not overlap; same-month handover is allowed |
| `gaps` | `max_gap_months = 3`, `gap_allowlist = {}`; stale entries fail |
| `skills` | `shared_skill_keywords = []`; case-insensitive uniqueness across groups, stale entries fail |
| `required_fields` | `required_fields = {}`; section names map to lists of nonempty string fields |
| `dates` | `date_format = "YYYY-MM"`; also accepts policies `YYYY` and `YYYY-MM-DD` |
| `codespell` | `codespell_ignore_words = []`; checks working directory using project skip settings; excludes `dist`, `.git`, `.venv` |
| `page_budget` | `page_budget = 2`; Chromium PDF page count; or a per-variant table, e.g. `page_budget = { "2-page" = 2, "one-page" = 1 }` |
| `header` | Screen and print contact items share a top offset; `screen_width = 1280`, `print_content_width = 688` CSS pixels |
| `page_breaks` | No PDF page break inside a role, nor inside a company block that fits one page; `print_content_height = 1009` CSS pixels |

### Which cuts are checked

`required_sections`, `role_highlights`, `quantified`, `page_budget`, `header` and `page_breaks` check cuts, not the
whole document. `published_variants = []` selects every variant with
`publish = true`, in `variants.toml` order, or all entries if none is
published. A list, e.g. `published_variants = ["one-page"]`, selects those
variants instead. A scalar `page_budget` binds every checked cut; a table binds
only the cuts it names, so an unnamed cut (a complete CV, say) has no budget.

`variant_exemptions` drops one of those variant rules for one cut, e.g.
`variant_exemptions = { full = ["quantified"] }` when the complete cut keeps
unquantified internships. Every variant name in `published_variants`, a budget
table or `variant_exemptions` must exist in `variants.toml`.

Breaking change in 0.2.0: `published_variant = "name"` became
`published_variants = ["name"]`, and the check now covers every published cut
by default. The old key fails with that hint.

The default print width is A4 minus two 14 mm margins at 96 dpi, and the
default print height A4 minus two 15 mm margins. Custom themes with different
margins should override both. Variant `style` tokens are applied to the HTML
and footer used by all three Chromium rules, including the unbroken height
measurement. Classic theme margins are fixed, so token overrides do not change
these dimensions. See [variant styling](development.md#per-variant-design-tokens).

### How `page_breaks` finds page breaks

Pagination is read back from the printed PDF, not predicted. The rule prints
each checked cut through the same code path as `resume build`, after pinning
two invisible 1 px links to every `.company` and `.role` block: one at its top
edge, one at its bottom edge. They are absolutely positioned, so layout does
not move, and Chromium writes each into the PDF on the page where that edge
was laid out. A block whose two edges land on different pages was split.

A split role always fails. A split company fails when its unbroken height,
measured from the same HTML laid out for print at `print_content_width`, fits
within `print_content_height`. A company taller than a page may break, but
only between roles. Themes must mark company and role blocks with the
`company` and `role` classes; the classic theme keeps both with
`break-inside: avoid`.

Gap allowlist keys are `"endDate..startDate"` pairs in `YYYY-MM`, with a nonempty
reason as value. Roles wholly before the latest education end date do not
create career gaps; roles ending after that date do. Without education, all
roles participate. Comparisons use months, even with year-only or day-level
policies (year-only dates use January). Invalid dates are reported before
unsafe timeline comparisons, including when the date rule is disabled.
Missing work start dates also produce date violations.

Required fields apply to entries in sections that exist; they do not require
sections to exist. Sentence and length checks cover basics summary and work
prose, with length limits applying only to work. Spelling, typography and unit
checks traverse prose strings, excluding URLs, identifiers and variant metadata.
The spelling rule enforces a curated consistency list, not a full dictionary.

Each content repository owns its editorial policy and exceptions.
Toolkit tests use fictional fixtures; the example CLI tests exercise default policy.

### Required content after filtering

Both coverage rules are hard, run under `--fast`, and default to empty tables
(no requirements). Enable them through `enabled` like other rules.

```toml
[required_sections]
"*" = ["basics", "work", "education", "skills"]
"one-page" = ["education", "languages"]

[role_highlights]
"one-page" = { min = 1, since = "2010-06" }
```

Required sections use the union of `"*"` and the variant list: shared policy
cannot accidentally disappear when adding a variant-specific requirement.
Missing or empty top-level sections fail after filtering. Role minima count
nonblank highlights in each surviving work entry. With `since` (inclusive
`YYYY-MM`), only roles starting on/after that month qualify, and those source
roles must also survive filtering. Without `since`, dropped roles are exempt.
Diagnostics identify the source role and the `x-tags` or `x-highlights` entries
to change; no wording is generated. `min` must be a nonnegative integer.
Unknown variant names, invalid month dates and malformed tables are errors.
Only `required_sections` accepts the wildcard key.
