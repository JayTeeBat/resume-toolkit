# CV quality checks

`uv run resume check` reads `resume.json`, `variants.toml` and `resume-checks.toml`
from the working directory. Override them with a positional resume path,
`--variants PATH` and `--config PATH`. A missing policy uses defaults; a missing
variants file means the whole document is checked. Unknown keys, rule names,
wrong types and inconsistent limits are configuration errors.

`--fast` skips only `page_budget` and `header`. `--strict` makes soft warnings
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
| `codespell` | `codespell_ignore_words = []`; checks working directory using existing project skip settings |
| `page_budget` | `page_budget = 2`; Chromium PDF page count |
| `header` | Screen and print contact items share a top offset; `screen_width = 1280`, `print_content_width = 688` CSS pixels |

`published_variant = ""` selects the first variant with `publish = true`, or
all entries if none is published. This selection serves `quantified`,
`page_budget` and `header`; an explicit name must exist in `variants.toml`.
The default print width is A4 minus two 14 mm margins at 96 dpi. Custom themes
with different margins should override it.

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

The repository policy retains existing editorial decisions and exceptions.
Toolkit tests use fictional fixtures and never load the owner's CV. CI runs
`resume check` separately to apply this policy to the actual content.
