# Hesburgh Lecture matching

This pairs Notre Dame faculty with alumni clubs for the Hesburgh Lecture series.
It reads three spreadsheet exports, then builds several complete plans side by
side, each tuned for a different goal, so staff can choose one.

## Run it

```
pip install pandas
make match                       # or: python3 -m engine
```

This reads `club_info.csv`, `prof_info.csv`, `lecture_info.csv` and (if present)
`weights.json` from this folder. Results are written to `OUTPUTS/`:

| file | what's in it |
|---|---|
| `plan_comparison.csv` | one row per plan: clubs served, first choices, repeat speakers, ... |
| `<plan>_matches.csv` | who goes where, the suggested month, and a one-line reason |
| `<plan>_unmatched.csv` | clubs with no speaker, why not, and three professors to try |
| `data_issues.csv` | everything odd in the inputs (typos fixed, blank fields, missing forms) |

Staff who would rather not touch a terminal use the web app in `ui/`.

## The plans

| plan | best when you want... |
|---|---|
| **Recommended** (default) | the most clubs served, then each club's favourite lecture, no repeat speakers and faculty spread out |
| **Best fit** | the strongest overall content match, favouring large and engaged clubs |
| **Most clubs served** | as many clubs as possible with a speaker, every club counting equally |
| **Balanced** | more faculty involved, no repeat speakers, professors sent where they asked to go |
| **Clubs' top choices** | as many clubs as possible getting the exact lecture they ranked first |

Every plan follows the same hard rules. Each club gets at most one speaker. No
professor goes past their `# of Events`. Every pair shares at least one month
and at least one requested theme or lecture.

## Spreadsheet columns

The engine finds columns **by name, not by position**. You can add new columns,
reorder them or delete ones it doesn't use, and nothing breaks. Small changes to
a name are also handled automatically: capitals, spaces, punctuation, a typo,
or a known alternative such as "Club Name" for "Club Check".

### Must exist, and keep these names

If one of these is missing, that file can't be used. The problem shows up as an
error in `data_issues.csv` and in the app. Renaming one is still safe if you
then point to the new name under **Settings → Columns** in the app (or in a
`columns.json`, see below).

| file | column | what it holds |
|---|---|---|
| club_info.csv | `ID Number` | unique club ID |
| club_info.csv | `Club Check` | club name |
| club_info.csv | `Availability` | months the club can host, e.g. `January,February,March` |
| club_info.csv | `Theme 1` … `Theme 5` | ranked requests, `Theme \| Lecture title- months` |
| prof_info.csv | `Recipient Full Name` | professor's name, spelled as in the lecture catalog |
| prof_info.csv | `Availability` | months free, or `All of the above` |
| lecture_info.csv | `Faculty` | professor who gives the lecture |
| lecture_info.csv | `Theme` | the lecture's theme |
| lecture_info.csv | `Topic` | the lecture title, spelled exactly as clubs request it |

### Used if present

If one of these is missing, matching still runs without that information, and
a note appears in the data issues.

| file | column | used for |
|---|---|---|
| club_info.csv | `Size` (AA … F), `HLS Score` | club priority |
| club_info.csv | `Region`, `Format` | travel wishes and format bonus |
| club_info.csv | `Invited 2026` | which clubs are in the program; the newest year's column is used |
| club_info.csv | `2025 Speaker`, `2024 Speaker`, … | avoiding repeat speakers; any year is picked up |
| club_info.csv | `2026 Assignment` | comparing plans with staff's own picks |
| prof_info.csv | `# of Events` | each professor's event limit (blank = 1) |
| prof_info.csv | `Title`, `Format(s)` | title boost and format bonus |
| prof_info.csv | `Participate in the Hesburgh Lecture program in 2026?` | skips anyone who answered No |
| prof_info.csv | `Particular clubs or areas of the country you are interested in traveling?` | travel wishes |
| lecture_info.csv | `Availability` | months the lecture is offered (blank = all year) |

**Adding columns:** `Theme 6`, `Theme 7`, … automatically become extra ranked
requests. A new `2026 Speaker` column is automatically treated as a past
speaker.

**Telling the code where things are:** when a column was renamed to something
the engine can't recognise, map it yourself, either in the app or in a JSON
file passed with `python3 -m engine --columns columns.json`:

```json
{ "club": { "size": "Club Tier", "themes": ["Pick 1", "Pick 2", "Pick 3"] },
  "prof": { "max_events": "How many talks?" } }
```

The field names to use are listed in `engine/columns.py`.

## Tuning

`weights.json` holds dials. 1 is the default, 0 switches a factor off and 2
doubles it:

```json
{ "size": 1, "engagement": 1, "title": 1, "choice_rank": 1,
  "repeat_penalty": 1, "spread": 1, "travel_bonus": 1 }
```

The old names (`size_weight`, `eng_weight`, `title_weight`) still work.

## Folder map

| | |
|---|---|
| `engine/` | the matching engine ([how it works](engine/README.md), [API for other code](engine/API.md)) |
| `ui/` | the staff web app |
| `analysis/` | the code review that started the rewrite |
| `legacy/` | the original scripts, kept for reference |
