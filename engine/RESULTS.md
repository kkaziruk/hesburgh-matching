# Matching engine upgrade: results

Run on Zack's inputs (club_info.csv, prof_info.csv, lecture_info.csv; identical to the
copies in the project folder) on 2026-10-15. Reproduce with:

```
python3 -m engine club_info.csv prof_info.csv lecture_info.csv --modes legacy_greedy,best_fit,most_clubs,balanced,top_choices --out OUTPUTS
```

## What was fixed

| Review item | Fix |
|---|---|
| 1. Five professors lost to name typos | Names are matched forgivingly and each fix is listed in `data_issues`. All 41 professors now have lectures. |
| 2. First professor row skipped | Only a real survey label row is dropped. Francisco Aragon is back. |
| 3. weights.json ignored and destructive | Weights are now multipliers (0 = ignore, 2 = double) and are actually applied. Old keys (`size_weight` ...) still load. |
| 4. Titles cut at first hyphen | The split happens at "- <Month>", so "Ever-Changing" and "Twentieth-Century" survive. |
| 5. Curly vs straight apostrophes | Normalised. Akron now gets credit for Chiang's LLM talk. |
| 6. Past speakers unused | Flagged on every match (`repeat_speaker`). Balanced avoids them. |
| 8. Crashes on blank size or score | These fall back to a middle value with a warning. A missing column gives a clear error. |
| (new) Lecture availability ignored | A lecture only counts if it is offered in a month both sides are free. |
| (new) Club ranking ignored | A club's Theme 1 request counts more than its Theme 5 request. |
| (new) Same-month double booking | Each match gets a `suggested_month`. A professor's events are placed in different months where possible. |

## The plans side by side (default weights, updated with Recommended)

| | Old greedy | **Recommended** | Best fit | Most clubs | Balanced |
|---|---|---|---|---|---|
| Clubs matched (of 52) | 40 | **40** | 40 | 40 | 40 |
| Got their exact 1st-choice lecture | 23 | **31** | 22 | 21 | 20 |
| Got a lecture they asked for | 38 | **40** | 38 | 39 | 39 |
| Repeat speakers | 1 | **0** | 1 | 1 | 0 |
| Professors used (of 41) | 25 | 26 | 24 | 25 | **31** |
| Same as staff's 2026 Assignment | 25 | **28** | 25 | 23 | 27 |
| Total score | 926 | 895 | **928** | 922 | 914 |

**Recommended** is the default. It ranks its goals strictly, and each one counts for more than everything below it:
1. Serve as many clubs as possible.
2. Give each club the lecture it ranked highest.
3. Avoid repeat speakers.
4. Spread events across faculty, honour travel wishes, and get the best content fit.

The 12 clubs without a speaker sent in no request form. For each of them, the unmatched sheet lists up to three professors who still have open slots. Professors who asked for that club by name come first (for example, David Go asked for Dallas). Staff can make those calls by hand.

Associate titles now get a smaller boost than full ones. "Associate Dean" is ×1.10 instead of ×1.20 for a dean. "Vice President and Associate Provost" counts as vice president (×1.25).

## Decisions

- 2026-10-15: Zack asked for the best matches that serve as many clubs as possible and make people happiest. That became the Recommended plan, which is now the default. Associate titles were lowered.
