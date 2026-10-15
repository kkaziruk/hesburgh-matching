"""Choose which pairs to make, given how much each pair is worth.

Rules every solution obeys: a club gets at most one professor, and a professor
gets at most `capacity` clubs.

`best_assignment` finds the provably best total. It gives each professor one
seat per event they can do (seat k may carry an extra cost, which is how
Balanced makes a 3rd event dearer than a 2nd), lets any club stay unseated, and
solves the resulting assignment problem exactly with the Hungarian algorithm.
At this size (about 50 clubs x 100 seats) that takes well under a second, so
no solver library is needed.
"""
from __future__ import annotations

from typing import Callable, Optional

Worth = Callable[[int, int], Optional[float]]   # (club, prof) -> value, or None if not allowed
SeatCost = Callable[[int, int], float]          # (prof, k-th event) -> extra cost

_FORBIDDEN = 1e12


def best_assignment(n_clubs: int, capacity: list[int], worth: Worth,
                    seat_cost: SeatCost | None = None) -> list[int | None]:
    """For each club, the professor it gets (or None), maximising total worth."""
    seats = [(p, k) for p, cap in enumerate(capacity) for k in range(1, cap + 1)]

    def cost(c: int, p: int, k: int) -> float:
        value = worth(c, p)
        if value is None:
            return _FORBIDDEN
        net = value - (seat_cost(p, k) if seat_cost else 0.0)
        return -net if net > 0 else _FORBIDDEN      # never make a pair worth nothing

    stay_unseated = [0.0] * n_clubs
    matrix = [[cost(c, p, k) for p, k in seats] + stay_unseated for c in range(n_clubs)]

    chosen = []
    for c, column in enumerate(hungarian(matrix)):
        real_seat = column < len(seats) and matrix[c][column] < _FORBIDDEN
        chosen.append(seats[column][0] if real_seat else None)
    return chosen


def greedy_assignment(n_clubs: int, capacity: list[int], worth: Worth) -> list[int | None]:
    """The original method: repeatedly take the most valuable remaining pair.
    Ties keep the original program's order (professor by professor)."""
    candidates = [(value, c, p) for p in range(len(capacity)) for c in range(n_clubs)
                  if (value := worth(c, p)) is not None]
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    chosen: list[int | None] = [None] * n_clubs
    used = [0] * len(capacity)
    for _, c, p in candidates:
        if chosen[c] is None and used[p] < capacity[p]:
            chosen[c] = p
            used[p] += 1
    return chosen


def hungarian(cost: list[list[float]]) -> list[int]:
    """Minimum-cost assignment of every row to a distinct column (rows <= columns).

    The classic O(rows^2 x columns) shortest-augmenting-path version with row and
    column potentials. Returns the column chosen for each row."""
    rows = len(cost)
    if rows == 0:
        return []
    cols = len(cost[0])
    row_pot, col_pot = [0.0] * (rows + 1), [0.0] * (cols + 1)
    owner = [0] * (cols + 1)          # owner[j] = row (1-based) holding column j; column 0 is a sentinel
    came_from = [0] * (cols + 1)

    for row in range(1, rows + 1):
        owner[0] = row
        col = 0
        best = [float("inf")] * (cols + 1)
        done = [False] * (cols + 1)
        while True:                    # grow shortest paths until a free column is reached
            done[col] = True
            r = owner[col]
            delta, next_col = float("inf"), 0
            for j in range(1, cols + 1):
                if done[j]:
                    continue
                reduced = cost[r - 1][j - 1] - row_pot[r] - col_pot[j]
                if reduced < best[j]:
                    best[j], came_from[j] = reduced, col
                if best[j] < delta:
                    delta, next_col = best[j], j
            for j in range(cols + 1):
                if done[j]:
                    row_pot[owner[j]] += delta
                    col_pot[j] -= delta
                else:
                    best[j] -= delta
            col = next_col
            if owner[col] == 0:
                break
        while col:                     # flip the augmenting path
            prev = came_from[col]
            owner[col] = owner[prev]
            col = prev

    assignment = [-1] * rows
    for j in range(1, cols + 1):
        if owner[j]:
            assignment[owner[j] - 1] = j - 1
    return assignment
