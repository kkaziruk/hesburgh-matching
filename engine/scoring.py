"""How good is professor P for club C?

A pair is *allowed* when the two share at least one month and at least one
requested theme or lecture. An allowed pair's score keeps the original recipe,
so the numbers stay familiar:

    points   = 10 per requested lecture the professor offers (in a shared month)
             +  5 per shared theme
             +  2 per shared month
             +  1 per shared talk format
             + 10 if staff already picked this professor (off by default)
             + up to 10 for professors' travel wishes (-6 when it goes against them; see geo.py)
    score    = points x club priority x title boost

Every number above has a dial in `Weights` (see WEIGHT_INFO for plain-English help).

with three corrections: a club's 1st choice counts more than its 5th, a
lecture counts only when it is offered in a month both sides are free, and
the weights scale the real per-club values instead of replacing them.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .geo import travel_fit
from .model import Club, Professor
from .text import MONTHS, clean, ordinal, same_person

TITLE_BOOST = {
    "provost": 1.30, "vice president": 1.25, "vice provost": 1.20, "dean": 1.20,
    "associate provost": 1.15, "director": 1.15, "associate dean": 1.10, "program director": 1.10,
    "assistant dean": 1.05, "associate professor": 1.05, "professor of the practice": 1.02,
    "teaching professor": 1.00, "assistant professor": 1.00, "professor": 1.00,
}
SIZE_VALUE = {"AA": 1.00, "A": 0.90, "B": 0.80, "C": 0.70, "D": 0.60, "E": 0.50, "F": 0.40}
ENGAGEMENT_BANDS = ((600, 1.00), (450, 0.90), (350, 0.80), (250, 0.70), (150, 0.60), (0, 0.55))
UNKNOWN = 0.5                     # size or engagement left blank
TITLE_BOOST_FROM_PRIORITY = 0.7   # only high-priority clubs get the title boost
MIN_POINTS = 0.01


# ------------------------------------------------------------------ weights

@dataclass
class Weights:
    """Dials staff can turn. 1 = default, 0 = ignore the factor, 2 = double it.
    WEIGHT_INFO below explains each one in plain English."""
    lecture_match: float = 1.0
    theme_match: float = 1.0
    month_overlap: float = 1.0
    format_match: float = 1.0
    choice_rank: float = 1.0
    size: float = 1.0
    engagement: float = 1.0
    title: float = 1.0
    repeat_penalty: float = 1.0
    spread: float = 1.0
    travel_bonus: float = 1.0
    staff_pick: float = 0.0

    _OLD_NAMES = {"size_weight": "size", "eng_weight": "engagement", "title_weight": "title"}

    @classmethod
    def coerce(cls, value) -> "Weights":
        """Weights, a dict (old weights.json names accepted) or None."""
        if isinstance(value, cls):
            return value
        known = {f.name for f in fields(cls)}
        chosen = {}
        for key, number in dict(value or {}).items():
            key = cls._OLD_NAMES.get(key, key)
            if key in known and number is not None:
                chosen[key] = max(0.0, float(number))
        return cls(**chosen)

    @classmethod
    def from_json(cls, source) -> "Weights":
        text = source.read() if hasattr(source, "read") else Path(source).read_text(encoding="utf-8")
        return cls.coerce(json.loads(text.decode("utf-8") if isinstance(text, bytes) else text))

    def as_dict(self) -> dict:
        return asdict(self)


ALL_PLANS = "All plans"
FAIRNESS_PLANS = "Recommended and Balanced"

WEIGHT_INFO = {
    "lecture_match": dict(
        label="Requested lecture",
        help="Points when the professor gives a lecture the club asked for by name (10 each at 1x). "
             "Raise it to favour exact talks over loose theme matches.",
        group="What the club asked for", applies_to=ALL_PLANS),
    "theme_match": dict(
        label="Shared theme",
        help="Points when the professor covers a theme the club asked for, even without the exact talk "
             "(5 each at 1x).",
        group="What the club asked for", applies_to=ALL_PLANS),
    "choice_rank": dict(
        label="Respect club's ranking",
        help="How much a club's 1st choice beats its 5th. At 1x each step down the list is worth 10% less; "
             "0 treats all five choices the same.",
        group="What the club asked for", applies_to=ALL_PLANS),
    "month_overlap": dict(
        label="Calendar flexibility",
        help="Points for each month both sides are free (2 each at 1x). More shared months make "
             "scheduling easier. One shared month is always required.",
        group="Logistics", applies_to=ALL_PLANS),
    "format_match": dict(
        label="Talk format",
        help="Points when the professor offers the format the club wants, such as a fireside chat "
             "(1 each at 1x).",
        group="Logistics", applies_to=ALL_PLANS),
    "size": dict(
        label="Club size",
        help="How much bigger clubs (AA, A) are favoured over smaller ones (E, F). 0 treats every size alike.",
        group="Which clubs come first", applies_to=ALL_PLANS + " except Most clubs served"),
    "engagement": dict(
        label="Club engagement",
        help="How much clubs with a high HLS Score are favoured. 0 ignores engagement.",
        group="Which clubs come first", applies_to=ALL_PLANS + " except Most clubs served"),
    "title": dict(
        label="Senior speakers for top clubs",
        help="Boost for deans, provosts and directors when matched with high-priority clubs "
             "(up to 1.3x at 1x). 0 treats every title alike.",
        group="Which clubs come first", applies_to=ALL_PLANS),
    "repeat_penalty": dict(
        label="Avoid repeat speakers",
        help="Penalty for sending a professor who spoke at this club in the last four years.",
        group="Fairness", applies_to=FAIRNESS_PLANS),
    "spread": dict(
        label="Spread events across faculty",
        help="Makes a professor's 2nd and 3rd events cost more, so more faculty take part. "
             "0 lets the best professors take every slot they offered.",
        group="Fairness", applies_to=FAIRNESS_PLANS),
    "travel_bonus": dict(
        label="Professors' travel wishes",
        help="How much to follow where professors said they'd like to go: clubs or cities they named, "
             "their states and regions, 'major cities only', a drive limit from South Bend. A named club "
             "earns up to 10 points at 1x, and going against a stated wish (a big-city person to a small "
             "town) costs up to 6. Recommended weighs it more heavily. 0 ignores travel wishes.",
        group="Fairness", applies_to=ALL_PLANS),
    "staff_pick": dict(
        label="Agree with staff's picks",
        help="Bonus when the professor is the one already in the club's '2026 Assignment' column "
             "(10 points at 1x). Off by default so the plans stay an independent second opinion.",
        group="Fairness", applies_to=ALL_PLANS),
}
for _key, _info in WEIGHT_INFO.items():
    _info.update(default=Weights.__dataclass_fields__[_key].default, min=0.0, max=3.0 if _key != "staff_pick" else 5.0)


# ------------------------------------------------------------------ club and professor factors

def engagement_value(hls_score: int | None) -> float:
    if hls_score is None:
        return UNKNOWN
    return next(value for floor, value in ENGAGEMENT_BANDS if hls_score >= floor)


def club_priority(club: Club, w: Weights) -> float:
    """Weighted average of size (65%) and engagement (35%), each between 0.4 and 1."""
    size_share, engagement_share = 0.65 * w.size, 0.35 * w.engagement
    if size_share + engagement_share == 0:
        return 1.0
    size = SIZE_VALUE.get(club.size, UNKNOWN)
    engagement = engagement_value(club.engagement)
    return (size_share * size + engagement_share * engagement) / (size_share + engagement_share)


def title_boost(prof: Professor, w: Weights) -> float:
    return 1.0 + w.title * (TITLE_BOOST.get(prof.title, 1.0) - 1.0)


def choice_factor(rank: int | None, w: Weights) -> float:
    """1st choice = 1.0, each later choice 10% less (scaled by w.choice_rank)."""
    return 1.0 if rank is None else max(0.2, 1.0 - 0.1 * w.choice_rank * (rank - 1))


# ------------------------------------------------------------------ the pair

@dataclass
class Pair:
    club: Club
    prof: Professor
    shared_months: list[str]
    shared_themes: list[str]
    lectures: list[tuple[int, str]]     # (club's rank for it, lecture title), best first
    shared_formats: list[str]
    choice_rank: int | None             # best-ranked request this pair satisfies
    fit: float                          # points, ignoring who the club is
    score: float                        # fit x club priority x title boost
    repeat: bool                        # professor already spoke here 2022-2025
    travel_fit: float                   # -1 (against their travel wishes) .. +1 (club they named)
    travel_note: str                    # why, e.g. "asked for San Diego by name"
    allowed: bool = False               # shares a month and a requested theme or lecture

    @property
    def travel(self) -> bool:
        return self.travel_fit > 0

    @property
    def first_choice_lecture(self) -> bool:
        return bool(self.lectures) and self.lectures[0][0] == 1

    def why(self) -> str:
        """One line a person can read: what makes this a good pair."""
        if self.lectures:
            rank, title = self.lectures[0]
            reasons = [f"{ordinal(rank)}-choice lecture '{title}'"]
            if len(self.lectures) > 1:
                reasons.append(f"+{len(self.lectures) - 1} more requested")
        else:
            reasons = [f"{ordinal(self.choice_rank)}-choice theme {self.shared_themes[0]}"]
        n = len(self.shared_months)
        reasons.append(f"{n} shared month{'' if n == 1 else 's'}")
        if self.travel_note:
            reasons.append(f"travel: {self.travel_note}")
        if self.repeat:
            reasons.append("REPEAT speaker")
        return "; ".join(reasons)


def score_pair(club: Club, prof: Professor, w: Weights) -> Pair:
    months = [m for m in MONTHS if m in club.months and m in prof.months]
    themes = [t for t in club.requested_themes if clean(t) in prof.themes]
    lectures = sorted(
        (r.rank, lecture.title)
        for r in club.requests
        if (lecture := prof.offers(r.title)) and any(m in lecture.months for m in months)
    )
    prof_formats = {clean(f) for f in prof.formats}
    formats = [f for f in club.formats if clean(f) in prof_formats]

    if lectures:
        rank = lectures[0][0]
    elif themes:
        rank = min(r.rank for r in club.requests if r.theme and clean(r.theme) in prof.themes)
    else:
        rank = None

    allowed = bool(months) and bool(themes or lectures)
    travel, travel_note = travel_fit(prof.travel_wishes, club.name, club.size, club.region)
    fit = 0.0
    score = 0.0
    if allowed:
        staff_choice = bool(club.staff_pick) and same_person(club.staff_pick, prof.name)
        fit = (10 * w.lecture_match * sum(choice_factor(r, w) for r, _ in lectures)
               + 5 * w.theme_match * len(themes) * choice_factor(rank, w)
               + 2 * w.month_overlap * len(months)
               + 1 * w.format_match * len(formats)
               + 10 * w.staff_pick * staff_choice
               + 6 * w.travel_bonus * travel)
        fit = max(fit, MIN_POINTS)      # an allowed pair is always worth something, even with dials at 0
        priority = club_priority(club, w)
        boost = title_boost(prof, w) if priority >= TITLE_BOOST_FROM_PRIORITY else 1.0
        score = fit * priority * boost

    return Pair(club, prof, months, themes, lectures, formats, rank, fit, score,
                repeat=any(same_person(prof.name, s) for s in club.past_speakers),
                travel_fit=travel, travel_note=travel_note, allowed=allowed)


class PairGrid:
    """Every club x professor pair, scored once, addressed as grid[club_i, prof_i]."""

    def __init__(self, clubs: list[Club], profs: list[Professor], w: Weights):
        self.clubs, self.profs, self.weights = clubs, profs, w
        self._pairs = {(c, p): score_pair(club, prof, w)
                       for c, club in enumerate(clubs) for p, prof in enumerate(profs)}

    def __getitem__(self, key: tuple[int, int]) -> Pair:
        return self._pairs[key]

    def allowed(self):
        """(club_i, prof_i, pair) for every allowed pair."""
        return [(c, p, pair) for (c, p), pair in self._pairs.items() if pair.allowed]

    def for_club(self, c: int) -> list[Pair]:
        return [self._pairs[c, p] for p in range(len(self.profs))]
