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
| `unit_spacing` | Built-in SI symbols require whitespace after numbers |
| `tense` | Built-in English verb lists; current role present, ended role past |
| `verb_led` | Highlights start with a recognized present/past verb or an `-ed` word |
| `quantified` | At least one digit in each published work entry's summary/highlights |
| `lengths` | `summary_sentences = 1`, `summary_soft_max = 25`, `summary_hard_max = 30`; minimum 1 word |
| `lengths` | `highlight_soft_range = [10, 30]`, `highlight_hard_range = [3, 40]`; whitespace-separated words |
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

`quantified`, `page_budget`, `header` and `page_breaks` check cuts, not the
whole document. `published_variants = []` selects every variant with
`publish = true`, in `variants.toml` order, or all entries if none is
published. A list, e.g. `published_variants = ["one-page"]`, selects those
variants instead. A scalar `page_budget` binds every checked cut; a table binds
only the cuts it names, so an unnamed cut (a complete CV, say) has no budget.

`variant_exemptions` drops one of those four rules for one cut, e.g.
`variant_exemptions = { full = ["quantified"] }` when the complete cut keeps
unquantified internships. Every variant name in `published_variants`, a budget
table or `variant_exemptions` must exist in `variants.toml`.

Breaking change in 0.2.0: `published_variant = "name"` became
`published_variants = ["name"]`, and the check now covers every published cut
by default. The old key fails with that hint.

The default print width is A4 minus two 14 mm margins at 96 dpi, and the
default print height A4 minus two 15 mm margins. Custom themes with different
margins should override both.

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
