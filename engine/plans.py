"""Turn a mode's choices into the tables staff read: matches, unmatched, summary."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

import pandas as pd

from .model import MatchData
from .modes import REGISTRY, Context, Mode, context_for
from .scoring import Pair, PairGrid, Weights
from .solver import best_assignment, greedy_assignment
from .text import clean, same_person

MODES = {key: (m.label, m.description) for key, m in REGISTRY.items()}
DEFAULT_MODES = ["recommended", "best_fit", "most_clubs", "balanced"]

MATCH_COLUMNS = ["club_id", "club", "region", "size", "engagement", "professor", "title", "score",
                 "suggested_month", "shared_months", "shared_themes", "shared_lectures", "shared_formats",
                 "choice_rank", "repeat_speaker", "prof_events", "prof_max_events", "staff_pick", "why"]
SUMMARY_LABELS = {
    "clubs_matched": "Clubs matched",
    "clubs_unmatched": "Clubs without a speaker",
    "first_choice_lectures": "Got their 1st-choice lecture",
    "requested_lecture_matches": "Got a lecture they asked for",
    "top_choice_matches": "Got their 1st-choice theme or lecture",
    "total_score": "Total match score",
    "avg_score": "Average match score",
    "profs_used": "Professors used",
    "profs_available": "Professors who could be used",
    "max_events_per_prof": "Most events for one professor",
    "profs_with_multiple_events": "Professors with 2+ events",
    "repeat_speakers": "Repeat speakers",
    "month_clashes": "Professors double-booked in a month",
    "staff_pick_agreement": "Same as staff's 2026 pick",
    "clubs_total": "Clubs in the program",
}
UNMATCHED_COLUMNS = ["club_id", "club", "region", "size", "engagement", "reason",
                     "suggestion_1", "suggestion_1_why", "suggestion_2", "suggestion_2_why",
                     "suggestion_3", "suggestion_3_why"]


@dataclass
class Plan:
    key: str
    label: str
    description: str
    matches: pd.DataFrame
    unmatched: pd.DataFrame
    summary: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        s = self.summary
        return f"<Plan {self.key}: {s.get('clubs_matched')} clubs, score {s.get('total_score')}>"


# ------------------------------------------------------------------ public

def run_plans(data: MatchData, weights=None, modes=None) -> dict[str, Plan]:
    """Score every pair once, then let each mode pick its plan."""
    modes = list(modes or DEFAULT_MODES)
    unknown = [m for m in modes if m not in REGISTRY]
    if unknown:
        raise ValueError(f"Unknown mode {unknown[0]!r}. Choose from: {', '.join(REGISTRY)}")
    grid = PairGrid(data.clubs, data.profs, Weights.coerce(weights))
    ctx = context_for(grid)
    return {key: build_plan(REGISTRY[key], grid, ctx) for key in modes}


def compare_plans(plans: dict[str, Plan]) -> pd.DataFrame:
    """One row per plan, one column per summary number."""
    return pd.DataFrame([{"plan": p.label, **p.summary} for p in plans.values()]).set_index("plan")


# ------------------------------------------------------------------ building a plan

def choose(mode: Mode, grid: PairGrid, ctx: Context) -> list[int | None]:
    """For each club, the index of the professor this mode gives it (or None)."""
    def worth(c: int, p: int):
        pair = grid[c, p]
        return mode.worth(pair, ctx) if pair.allowed else None

    capacity = [prof.max_events for prof in grid.profs]
    if mode.method == "greedy":
        return greedy_assignment(len(grid.clubs), capacity, worth)
    seat_cost = (lambda p, k: mode.seat_cost(k, ctx)) if mode.seat_cost else None
    return best_assignment(len(grid.clubs), capacity, worth, seat_cost)


def build_plan(mode: Mode, grid: PairGrid, ctx: Context) -> Plan:
    choice = choose(mode, grid, ctx)
    made = [grid[c, p] for c, p in enumerate(choice) if p is not None]
    events = Counter(p for p in choice if p is not None)
    events_by_name = {grid.profs[p].name: n for p, n in events.items()}
    months, clashes = suggest_months(made)

    matches = _table([match_row(pair, months[id(pair)], events_by_name[pair.prof.name]) for pair in made],
                     MATCH_COLUMNS, whole_numbers=("engagement", "choice_rank"))
    unmatched = _table([unmatched_row(c, grid, events) for c, p in enumerate(choice) if p is None],
                       UNMATCHED_COLUMNS, whole_numbers=("engagement",))
    return Plan(mode.key, mode.label, mode.description, matches, unmatched,
                summarize(made, grid, events, clashes))


def _table(rows, columns, whole_numbers=()) -> pd.DataFrame:
    table = pd.DataFrame(rows, columns=columns).sort_values("club", kind="stable").reset_index(drop=True)
    for col in whole_numbers:
        table[col] = table[col].astype("Int64")       # whole numbers that may be blank
    return table


# ------------------------------------------------------------------ months

def suggest_months(made: list[Pair]) -> tuple[dict[int, str], int]:
    """Pick a month for each match so no professor has two events in one month
    where that can be avoided. Returns {id(pair): month} and the number of
    professors who could not avoid a clash."""
    by_prof = defaultdict(list)
    for pair in made:
        by_prof[pair.prof.name].append(pair)
    months, clashes = {}, 0
    for pairs in by_prof.values():
        picked, forced = _distinct_months(pairs)
        months.update(picked)
        clashes += forced > 0
    return months, clashes


def _distinct_months(pairs: list[Pair]) -> tuple[dict[int, str], int]:
    """Exhaustive search; fine because one professor has only a few events."""
    order = sorted(pairs, key=lambda pair: len(pair.shared_months))   # most constrained first
    best = {"months": {}, "forced": len(pairs) + 1}

    def place(i: int, taken: frozenset, picked: dict, forced: int):
        if forced >= best["forced"]:
            return
        if i == len(order):
            best.update(months=picked, forced=forced)
            return
        pair = order[i]
        for month in pair.shared_months:
            if month not in taken:
                place(i + 1, taken | {month}, {**picked, id(pair): month}, forced)
        place(i + 1, taken, {**picked, id(pair): pair.shared_months[0]}, forced + 1)

    place(0, frozenset(), {}, 0)
    return best["months"], best["forced"]


# ------------------------------------------------------------------ rows

def match_row(pair: Pair, month: str, prof_events: int) -> dict:
    club, prof = pair.club, pair.prof
    return {
        "club_id": club.id, "club": club.name, "region": club.region, "size": club.size,
        "engagement": club.engagement, "professor": prof.name, "title": prof.title,
        "score": round(pair.score, 2), "suggested_month": month,
        "shared_months": "; ".join(pair.shared_months),
        "shared_themes": "; ".join(pair.shared_themes),
        "shared_lectures": "; ".join(title for _, title in pair.lectures),
        "shared_formats": "; ".join(pair.shared_formats),
        "choice_rank": pair.choice_rank, "repeat_speaker": pair.repeat,
        "prof_events": prof_events, "prof_max_events": prof.max_events,
        "staff_pick": club.staff_pick, "why": pair.why(),
    }


def unmatched_row(c: int, grid: PairGrid, events: Counter) -> dict:
    club = grid.clubs[c]
    reason, suggestions = explain_unmatched(c, grid, events)
    row = {"club_id": club.id, "club": club.name, "region": club.region, "size": club.size,
           "engagement": club.engagement, "reason": reason}
    for i in range(3):
        name, why = suggestions[i] if i < len(suggestions) else ("", "")
        row[f"suggestion_{i + 1}"], row[f"suggestion_{i + 1}_why"] = name, why
    return row


def explain_unmatched(c: int, grid: PairGrid, events: Counter) -> tuple[str, list[tuple[str, str]]]:
    """Why a club got nobody, plus up to three professors worth a phone call."""
    club = grid.clubs[c]
    if not club.submitted_form:
        return "No request form submitted", still_free(c, grid, events)
    if not club.months:
        return "Missing availability", still_free(c, grid, events)
    if not club.requests:
        return "No themes or lectures requested", still_free(c, grid, events)

    pairs = grid.for_club(c)
    if not any(pair.shared_months for pair in pairs):
        return "No shared months with any professor", []

    allowed = sorted((pair for pair in pairs if pair.allowed), key=lambda pair: pair.score, reverse=True)
    if not allowed:
        nearest = sorted(pairs, key=lambda pair: (bool(pair.shared_themes or pair.lectures),
                                                  len(pair.shared_months)), reverse=True)
        return "No content overlap with any available professor", [
            (pair.prof.name, "near miss: " + ("no shared month" if not pair.shared_months
                                              else "no requested theme or lecture"))
            for pair in nearest[:3]]

    suggestions, any_open_seat = [], False
    for pair in allowed[:3]:
        used, cap = events[grid.profs.index(pair.prof)], pair.prof.max_events
        open_seats = cap - used
        any_open_seat |= open_seats > 0
        state = (f"fully booked ({used}/{cap})" if open_seats <= 0
                 else f"{open_seats} open slot{'s' if open_seats > 1 else ''}")
        suggestions.append((pair.prof.name, f"score {pair.score:.1f}; {state}; {pair.why()}"))
    reason = ("Left out so suitable professors are not overloaded" if any_open_seat
              else "All suitable professors are fully booked")
    return reason, suggestions


def still_free(c: int, grid: PairGrid, events: Counter) -> list[tuple[str, str]]:
    """For a club that never told us what it wants: professors with room left,
    those who asked to visit the area first, never a recent speaker."""
    club, options = grid.clubs[c], []
    for p, prof in enumerate(grid.profs):
        pair, open_seats = grid[c, p], prof.max_events - events[p]
        if open_seats <= 0 or pair.repeat or not prof.lectures:
            continue
        named = clean(club.name.split("/")[0]) in clean(prof.travel_wishes)
        note = f"{open_seats} open slot{'s' if open_seats > 1 else ''}"
        if named:
            note += f"; asked for {club.name} by name"
        elif pair.travel:
            note += "; asked to visit this area"
        options.append(((named, pair.travel, open_seats, len(prof.months)), prof.name, note))
    options.sort(key=lambda option: option[0], reverse=True)
    return [(name, f"still free: {note}") for _, name, note in options[:3]]


# ------------------------------------------------------------------ summary

def summarize(made: list[Pair], grid: PairGrid, events: Counter, clashes: int) -> dict:
    n, total = len(made), sum(pair.score for pair in made)
    return {
        "clubs_matched": n,
        "clubs_total": len(grid.clubs),
        "clubs_unmatched": len(grid.clubs) - n,
        "profs_used": len(events),
        "profs_available": len({p for _, p, _ in grid.allowed()}),
        "total_score": round(total, 1),
        "avg_score": round(total / n, 2) if n else 0.0,
        "top_choice_matches": sum(pair.choice_rank == 1 for pair in made),
        "first_choice_lectures": sum(pair.first_choice_lecture for pair in made),
        "requested_lecture_matches": sum(bool(pair.lectures) for pair in made),
        "repeat_speakers": sum(pair.repeat for pair in made),
        "max_events_per_prof": max(events.values(), default=0),
        "profs_with_multiple_events": sum(count > 1 for count in events.values()),
        "month_clashes": clashes,
        "staff_pick_agreement": sum(bool(pair.club.staff_pick) and same_person(pair.club.staff_pick, pair.prof.name)
                                    for pair in made),
    }
