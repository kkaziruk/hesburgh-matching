# Matching engine API

Status: **implemented and tested** (2026-10-15, `python3 -m unittest engine.tests.test_engine`). The
shape below will not change without a note here. The interface should import only
what is listed in this file.

Requires Python 3.10+ and `pandas` only. The optimal solver is built in (pure Python,
runs in about a second). No scipy, networkx or matplotlib.

```python
from engine import load_inputs, data_issues, run_plans, compare_plans, Weights
from engine import detect_columns, COLUMN_SPEC, MODES, SUMMARY_LABELS

data   = load_inputs(club_csv, prof_csv, lecture_csv)   # paths or file-like (BytesIO / Streamlit UploadedFile)
issues = data_issues(data)                              # list[dict]
plans  = run_plans(data, weights=None)                  # dict[str, Plan]
table  = compare_plans(plans)                           # DataFrame, one row per plan
```

`run_plans` is pure: no files are written. The UI exports `plan.matches` /
`plan.unmatched` itself (`df.to_csv`, `df.to_excel`).

## load_inputs(club_csv, prof_csv, lecture_csv, columns=None) -> MatchData

Accepts a path (`str` / `Path`) or a binary or text file-like object for each file.
Handles UTF-8 with or without BOM, and cp1252. Never raises on messy data: bad rows
and missing columns are reported through `data_issues`. Optional `columns=` override,
see "Column mapping".

`MatchData` attributes the UI may read: `clubs` (list), `profs` (list),
`n_clubs`, `n_profs`.

Also exported: `MODES` (`{key: (label, description)}`, includes `legacy_greedy`) and
`DEFAULT_MODES`.
`SUMMARY_LABELS` maps each summary key to plain English for display (e.g.
`first_choice_lectures` -> "Got their 1st-choice lecture"), in a sensible display order.

## Column mapping

Columns are found by meaning, not by position or exact spelling (see README.md
"Spreadsheet columns" and `columns.py`). Group keys are `"club"`, `"prof"`, `"lecture"`.

- `COLUMN_SPEC`: `{"club" | "prof" | "lecture": [{field, label, required, multi, default, meaning}]}`.
  `default` is a list of today's header(s). `multi=True` for `themes` (Theme 1-5, in rank
  order) and `past_speakers` (year columns, newest first).
- `detect_columns(club_csv, prof_csv, lecture_csv, columns=None)` returns
  `{"club": {"headers": [...all headers...], "mapping": {field: header | [headers] | None}}, ...}`
  without loading the data. The `columns` override wins over detection.
- `load_inputs(club_csv, prof_csv, lecture_csv, columns=None)` takes the same override,
  e.g. `{"club": {"size": "Club Tier", "themes": ["Pick 1", "Pick 2"]}}`. Fields left out
  are detected automatically. `data.columns` holds the mapping actually used.

Detection order per field: override, then the usual header or a known alternative
(ignoring case, spaces and punctuation), then a pattern (`Theme N`, `YYYY Speaker`,
`Invited YYYY` and `YYYY Assignment`, where the newest year wins), then a close spelling.
Extra columns are ignored.

**Missing columns never raise** (this replaces the earlier ValueError). A missing
*required* field gives an `error` issue of kind `missing_column` naming the file and
column, and that file's rows are skipped, so plans come back empty instead of crashing.
A missing optional field gives an `info` note. An override naming a header that isn't
in the file is an `error`.

## data_issues(data) -> list[dict]

Each item: `{"severity", "kind", "subject", "message"}`

- `severity`: `"error"` (data is lost, e.g. a professor with no lectures), `"warning"` (matching still works but something looks off), `"info"`.
- `kind` values: `missing_column`, `column_matched` (info: a close spelling was used), `empty_file`, `name_mismatch` (fuzzy-fixed name join, message says what it matched to), `prof_no_lectures`, `missing_availability`, `blank_size`, `blank_score`, `unknown_title`, `lecture_not_found` (a club requested a lecture title that is not in the catalog), `dropped_row`, `declined`.
- `subject`: the club or professor name.

Sorted errors first.

## run_plans(data, weights=None, modes=None) -> dict[str, Plan]

`modes` defaults to `["recommended", "best_fit", "most_clubs", "balanced"]`. Show `recommended` first and iterate the dict rather than hard-coding the keys. `"top_choices"` and `"legacy_greedy"` are available on request. Also accepted:
`"legacy_greedy"` (the old algorithm on the cleaned data, for comparison only).
Dict order follows `modes`.

`weights` is a `Weights` or a plain dict with any of these keys (defaults shown):

| key | default | meaning |
|---|---|---|
| `size` | 1.0 | how much club size counts in club priority (0 = ignore) |
| `engagement` | 1.0 | how much HLS engagement counts in club priority (0 = ignore) |
| `title` | 1.0 | strength of the professor-title boost (0 = no boost, 2 = double) |
| `choice_rank` | 1.0 | how much a club's 1st-choice request beats its 5th (0 = all equal) |
| `repeat_penalty` | 1.0 | Balanced only: penalty for a speaker the club had in 2022-2025 |
| `spread` | 1.0 | Balanced only: penalty for giving one professor several events |
| `travel_bonus` | 1.0 | Balanced only: bonus when the club is in a professor's preferred area |

These are multipliers on the real per-club and per-professor values. They never
replace them (the old weights.json bug). `Weights.from_json(path)` reads a
weights.json file with these keys.

Hard rules in every mode: a club gets at most one speaker; a professor never
exceeds their `# of Events`; a pair needs at least one shared month and shared
content (theme or lecture).

### The modes

| key | label | what it optimises |
|---|---|---|
| `recommended` | Recommended | **Default.** Most clubs served first, then each club's highest-ranked lecture, then no repeat speakers, then balanced fit. Each priority outranks everything after it. |
| `best_fit` | Best fit | Highest total match score (provably optimal, not greedy). |
| `most_clubs` | Most clubs served | Serves the most clubs possible, then the best fit among those plans; every club counts equally regardless of size. |
| `balanced` | Balanced | Best fit minus penalties for repeat speakers and stacking events on one professor, plus a bonus for professors' preferred travel areas. |
| `top_choices` | Clubs' top choices | Gives as many clubs as possible the exact lecture they ranked highest (Theme 1 before Theme 2 ...), then best fit. |

## Plan

Attributes:

- `key` (`"best_fit"`, ...), `label` (`"Best fit"`), `description` (one sentence for staff).
- `matches`: `pandas.DataFrame`, one row per assigned club, sorted by club name.
- `unmatched`: `pandas.DataFrame`, one row per club with no speaker.
- `summary`: `dict` (below).

### Plan.matches columns

| column | type | notes |
|---|---|---|
| `club_id` | str | |
| `club` | str | |
| `region` | str | |
| `size` | str | AA ... F |
| `engagement` | int or None | HLS Score |
| `professor` | str | |
| `title` | str | normalized title, e.g. "associate professor" |
| `score` | float | match score (comparable across plans) |
| `suggested_month` | str | a shared month that keeps this professor's events in different months where possible |
| `shared_months` | str | "; "-joined |
| `shared_themes` | str | |
| `shared_lectures` | str | |
| `shared_formats` | str | |
| `choice_rank` | int or None | which of the club's Theme 1-5 requests this covers (1 = top choice) |
| `repeat_speaker` | bool | professor spoke to this club 2022-2025 |
| `prof_events` | int | events this professor has in this plan |
| `prof_max_events` | int | |
| `staff_pick` | str | the club's "2026 Assignment" value, if any |
| `why` | str | short plain-English reason, e.g. "1st-choice lecture 'Decoding AI'; 3 shared months" |

### Plan.unmatched columns

`club_id`, `club`, `region`, `size`, `engagement`, `reason`, then
`suggestion_1`, `suggestion_1_why`, `suggestion_2`, `suggestion_2_why`,
`suggestion_3`, `suggestion_3_why` (blank when there are none).

`reason` is one of: "No request form submitted", "Missing availability", "No themes or
lectures requested", "No shared months with any professor", "No content overlap with any
available professor", "All suitable professors are fully booked", "Left out so suitable
professors are not overloaded" (Balanced only). For clubs with no form or no requests, the
suggestions list professors with open slots, starting with those who asked for the club by
name or for its area. The why column then begins "still free:".

### Plan.summary keys

| key | meaning |
|---|---|
| `clubs_matched` | int |
| `clubs_total` | int |
| `clubs_unmatched` | int |
| `profs_used` | int |
| `profs_available` | int (professors with at least one viable club) |
| `total_score` | float |
| `avg_score` | float |
| `top_choice_matches` | clubs whose match covers their 1st-choice request (lecture or theme) |
| `first_choice_lectures` | clubs that got the exact lecture they ranked 1st |
| `requested_lecture_matches` | clubs that got any lecture they asked for |
| `repeat_speakers` | int |
| `max_events_per_prof` | int |
| `profs_with_multiple_events` | int |
| `month_clashes` | professors with two events forced into the same month |
| `staff_pick_agreement` | int: matches equal to the "2026 Assignment" column |

## compare_plans(plans) -> DataFrame

One row per plan with the label plus the summary keys above, ready for a
side-by-side table.

## Command line

`python3 -m engine` (reads the three CSVs and weights.json from the current folder), or
`python3 -m engine club_info.csv prof_info.csv lecture_info.csv --out OUTPUTS/`
writes `<mode>_matches.csv`, `<mode>_unmatched.csv`, `data_issues.csv` and
`plan_comparison.csv`. Options: `--weights weights.json`, `--modes best_fit,balanced`.
