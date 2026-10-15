"""The matching modes. Each one is a single idea: what a pair is worth.

Adding a mode is one decorated function:

    @mode("my_mode", "My mode", "One sentence staff will read.")
    def my_mode(pair, ctx):
        return pair.score          # or None to forbid the pair

The solver then finds the plan with the highest total worth. A mode can also
make each extra event for the same professor cost more (`seat_cost`) or ask for
the old greedy method instead of the exact one (`method="greedy"`).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable, Optional

from .scoring import Pair, PairGrid, Weights


@dataclass(frozen=True)
class Context:
    weights: Weights
    typical_score: float          # median score of all allowed pairs, a natural unit


@dataclass(frozen=True)
class Mode:
    key: str
    label: str
    description: str
    worth: Callable[[Pair, Context], Optional[float]]
    seat_cost: Optional[Callable[[int, Context], float]] = None   # cost of a professor's k-th event
    method: str = "exact"


REGISTRY: dict[str, Mode] = {}


def mode(key: str, label: str, description: str, *, seat_cost=None, method: str = "exact"):
    def register(worth):
        REGISTRY[key] = Mode(key, label, description, worth, seat_cost, method)
        return worth
    return register


def context_for(grid: PairGrid) -> Context:
    scores = [pair.score for _, _, pair in grid.allowed()]
    return Context(grid.weights, statistics.median(scores) if scores else 0.0)


# ------------------------------------------------------------------ the modes

EVERY_CLUB_FIRST = 1000.0   # bigger than any other term, so one more club always wins
PREFERENCE_FIRST = 100.0    # one step in a club's ranking beats any difference in fit


def club_preference(pair) -> float:
    """How much the club wanted this: 5 for its 1st-choice lecture down to 1 for its 5th;
    a theme-only match counts half."""
    if pair.lectures:
        return max(1, 6 - pair.lectures[0][0])
    return max(0.5, (6 - pair.choice_rank) / 2)


@mode("recommended", "Recommended",
      "Serves as many clubs as possible, then gives each the lecture it wanted most, while "
      "avoiding repeat speakers, spreading events across faculty and honouring travel wishes.",
      seat_cost=lambda k, ctx: ctx.weights.spread * 0.3 * ctx.typical_score * (k - 1))
def recommended(pair, ctx):
    # Priorities, each worth more than everything below it:
    #   1. one more club served                       1000
    #   2. the club's preference (one rank step)       100
    #   3. no repeat speaker                            60
    #   4. professors' travel wishes                  up to 40
    #   5. balanced fit (score, spread)                ~10-50
    w = ctx.weights
    value = EVERY_CLUB_FIRST + PREFERENCE_FIRST * club_preference(pair) + pair.score
    if pair.repeat:
        value -= 60 * w.repeat_penalty
    value += 40 * w.travel_bonus * pair.travel_fit
    return value


@mode("best_fit", "Best fit",
      "The highest possible total match score: strongest content fit, favouring large, engaged clubs.")
def best_fit(pair, ctx):
    return pair.score


@mode("most_clubs", "Most clubs served",
      "Serves as many clubs as possible and treats every club equally, regardless of size or engagement.")
def most_clubs(pair, ctx):
    return EVERY_CLUB_FIRST + pair.fit


@mode("balanced", "Balanced",
      "Strong fit while spreading events across more faculty, avoiding repeat speakers and "
      "honouring professors' preferred travel areas.",
      seat_cost=lambda k, ctx: ctx.weights.spread * 0.3 * ctx.typical_score * (k - 1))
def balanced(pair, ctx):
    w = ctx.weights
    value = pair.score
    if pair.repeat:
        value *= max(0.0, 1.0 - 0.6 * w.repeat_penalty)
    value *= max(0.1, 1.0 + 0.2 * w.travel_bonus * pair.travel_fit)
    return value


@mode("top_choices", "Clubs' top choices",
      "Gives as many clubs as possible the exact lecture they ranked highest, then the best fit.")
def top_choices(pair, ctx):
    return PREFERENCE_FIRST * club_preference(pair) + pair.score


@mode("legacy_greedy", "Old method (greedy)",
      "The previous greedy algorithm on the cleaned data, for comparison.", method="greedy")
def legacy_greedy(pair, ctx):
    return pair.score
