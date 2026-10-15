# How the engine works

```
 club_info.csv ─┐
 prof_info.csv ─┼─▶ loader ──▶ clubs, professors, lectures ──▶ scoring ──▶ every pair, scored once
 lecture_info ──┘      │                                                       │
                       └─▶ data issues                                         ▼
                                                     modes (what is a pair worth?) ──▶ solver ──▶ plans
```

Read the files in this order. Each one does one job.

| file | job |
|---|---|
| `text.py` | Forgiving text helpers. Curly quotes, double spaces, "Fr.", "C.S.C." and one-letter typos all compare equal. Month ranges like "November-February" are expanded. |
| `columns.py` | Finds each column by meaning. Renamed, reordered or added columns still work, and staff can override any choice. |
| `geo.py` | Reads professors' travel answers (places, states, regions, "major cities", drive limits) and scores how well each club suits them. |
| `geo_data.py` | The bundled location table: every club's state, coordinates and metro size, plus cities and regions professors mention. No internet needed. |
| `model.py` | The nouns: `Club`, `Professor`, `Lecture`, `Request`. |
| `loader.py` | CSV → model. Never crashes on a messy row; every repair becomes a readable issue. |
| `scoring.py` | How good one professor is for one club (`Pair`), plus the `Weights` dials. |
| `modes.py` | One small function per plan, saying what a pair is worth in that plan. |
| `solver.py` | Picks the pairs: an exact Hungarian solver (provably best total), or the old greedy method. |
| `plans.py` | Turns picks into the matches, unmatched and summary tables, and suggests months. |

## Scoring a pair

A pair is allowed only if the club and professor share a month and share a
requested theme or lecture. An allowed pair earns:

- 10 points for each requested lecture the professor offers, in a month both sides are free
- 5 points for each shared theme
- 2 points for each shared month
- 1 point for each shared talk format
- up to 6 points when the club suits the professor's travel wishes, or up to −3.6 when it goes against them (see `geo.py`)

A club's later choices earn a little less: each step down its Theme 1-5 list
costs 10%. The points are then multiplied by:

- the club's **priority**: 65% club size and 35% engagement, each between 0.4 and 1
- the professor's **title boost**, up to ×1.30. High-priority clubs only.

## Adding a plan

```python
# modes.py
@mode("regional", "Regional", "Keeps each professor's events in one region.")
def regional(pair, ctx):
    return pair.score            # what this pair is worth; None forbids it
```

Plans can also charge for each extra event a professor takes. Balanced does
this to spread events out:

```python
seat_cost=lambda k, ctx: ctx.weights.spread * 0.3 * ctx.typical_score * (k - 1)
```

The new plan shows up automatically in `MODES`, on the command line and in the app.

## Tests

`make test` runs 29 checks. They cover the parsing fixes, the hard rules in every
plan, the tradeoffs each plan promises, messy and uploaded inputs, renamed,
shuffled and extra columns (which must give identical plans), and the solver
against brute force on random problems.
