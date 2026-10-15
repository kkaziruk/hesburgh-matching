"""The nouns of the problem: lectures, professors, clubs and their requests."""
from __future__ import annotations

from dataclasses import dataclass, field

from .text import clean


@dataclass
class Lecture:
    theme: str
    title: str
    months: list[str]
    listed_under: str            # faculty name exactly as the catalog spells it


@dataclass
class Professor:
    name: str
    title: str                   # normalised, e.g. "associate professor"
    title_raw: str
    months: list[str]
    max_events: int
    formats: list[str]
    travel_wishes: str           # free text: "Any Bay Area club; San Diego; DC"
    lectures: list[Lecture] = field(default_factory=list)

    @property
    def themes(self) -> set[str]:
        return {clean(lecture.theme) for lecture in self.lectures}

    def offers(self, title: str | None) -> Lecture | None:
        key = clean(title)
        return next((lec for lec in self.lectures if clean(lec.title) == key), None) if key else None


@dataclass
class Request:
    rank: int                    # 1 = the club's Theme 1, its top choice
    theme: str | None
    title: str | None


@dataclass
class Club:
    id: str
    name: str
    size: str                    # AA, A ... F, or "" when unknown
    region: str
    engagement: int | None       # HLS Score
    months: list[str]
    formats: list[str]
    requests: list[Request]
    past_speakers: list[str]
    staff_pick: str              # the "2026 Assignment" column

    @property
    def submitted_form(self) -> bool:
        return bool(self.requests or self.months)

    @property
    def requested_themes(self) -> list[str]:
        seen: dict[str, str] = {}
        for r in self.requests:
            if r.theme:
                seen.setdefault(clean(r.theme), r.theme)
        return list(seen.values())


@dataclass
class MatchData:
    clubs: list[Club]
    profs: list[Professor]
    lectures: list[Lecture]
    issues: list[dict]
    columns: dict = field(default_factory=dict)   # {"club": {field: header}, ...} as actually used

    @property
    def n_clubs(self) -> int:
        return len(self.clubs)

    @property
    def n_profs(self) -> int:
        return len(self.profs)
