"""Where professors would like to go, and how well a club fits that.

Professors answer "Particular clubs or areas of the country you are interested
in traveling?" in free text. `read_wishes` turns an answer into:

    places      clubs or cities they named ("San Diego", "NYC", "Lexington, KY")
    states      states they named ("California", "FL")
    regions     regions they named ("mountain west", "East coast", "Latin America")
    styles      "major cities", "AA and A sized clubs", "4 hour drive from South Bend"
    anywhere    "I'll go anywhere", "open to anything" (no penalty for any club)

`travel_fit` then scores one club from -1 (goes against what they said) to +1
(the club they asked for by name), with a one-line reason. A blank answer is
neutral (0). Everything is looked up in geo_data.py; nothing calls the internet.
"""
from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .geo_data import CITIES, CLUBS, REGIONS, SOUTH_BEND, STATE_ABBREVIATIONS, STATES
from .text import clean

STATE_NAMES = {code: name.title() for name, code in STATES.items() if name != "pennsylvannia"}
STATE_NAMES.update({"DC": "Washington, D.C.", "CAN": "Canada", "BO": "Bolivia", "CO_": "Colombia",
                    "HK": "Hong Kong", "PR": "Puerto Rico"})

_PAST = re.compile(r"already (done|been|presented|visited)|have (already )?presented|i have presented")
_ANYWHERE = re.compile(r"\banywhere\b|\bany (club|market|city)\b|where ?ever|open to (anything|speaking)|"
                       r"doesn'?t (really )?matter|willing to go|\bi'?m open\b|\bi am open\b|any club")
_BIG_CITY = re.compile(r"major cit|big cit|large cit|major metro|big metro")
_SIZE = re.compile(r"\b(aa|a)\b(?: and \b(aa|a)\b)? sized clubs")
_DRIVE = re.compile(r"(\d+) ?hours? drive")

NEAR_KM, SHORT_TRIP_KM, DRIVE_KM_PER_HOUR = 80, 250, 100


@dataclass
class Wishes:
    raw: str
    places: list[tuple[str, float, float]] = field(default_factory=list)
    clubs: set[str] = field(default_factory=set)
    states: set[str] = field(default_factory=set)
    regions: list[tuple[str, set[str]]] = field(default_factory=list)
    big_city: bool = False
    sizes: set[str] = field(default_factory=set)
    drive_hours: int | None = None
    anywhere: bool = False

    @property
    def stated(self) -> bool:
        return bool(self.places or self.clubs or self.states or self.regions or self.big_city
                    or self.sizes or self.drive_hours)

    def summary(self) -> str:
        """Readable one-liner for RESULTS.md and the app."""
        bits = []
        if self.clubs:
            bits.append("clubs: " + ", ".join(sorted(self.clubs)))
        extra_places = [p for p, *_ in self.places if p not in self.clubs]
        if extra_places:
            bits.append("near: " + ", ".join(extra_places))
        if self.states:
            bits.append("states: " + ", ".join(sorted(STATE_NAMES.get(s, s) for s in self.states)))
        if self.regions:
            bits.append("regions: " + ", ".join(label for label, _ in self.regions))
        if self.big_city:
            bits.append("prefers major cities")
        if self.sizes:
            bits.append("prefers " + "/".join(sorted(self.sizes)) + " clubs")
        if self.drive_hours:
            bits.append(f"within {self.drive_hours}h drive of South Bend")
        if self.anywhere:
            bits.append("happy to go anywhere")
        return "; ".join(bits) or "no preference"


def _find(phrase: str, text: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", text) is not None


PLACED = "§"   # marks text already read as a place


def _blank(phrase: str, text: str) -> str:
    return re.sub(rf"(?<![\w-]){re.escape(phrase)}(?![\w-])", PLACED, text)


def _find_close(phrase: str, text: str) -> bool:
    """Tolerates a typo in longer names: 'San Francisoc'."""
    if len(phrase) < 8:
        return False
    words, n = re.findall(r"[a-z.']+", text), len(phrase.split())
    return any(difflib.SequenceMatcher(None, " ".join(words[i:i + n]), phrase).ratio() >= 0.88
               for i in range(len(words) - n + 1))


def _drop_qualifiers(text: str) -> str:
    """'San Diego, California' and 'Dallas, TX' name a city, not the whole state."""
    states = "|".join(sorted(map(re.escape, [*STATES, *STATE_ABBREVIATIONS]), key=len, reverse=True))
    return re.sub(rf"{PLACED}\s*(?:,\s*|\(\s*)(?:{states})\b\)?", PLACED, text)


@lru_cache(maxsize=None)
def read_wishes(answer: str) -> Wishes:
    wishes = Wishes(answer or "")
    # Places they have already been are history, not wishes.
    sentences = [clean(s) for s in re.split(r"[!?\n]+|(?<![Ss]t)\.\s", answer or "")]
    text = " . ".join(s for s in sentences if s and not _PAST.search(s))
    if not text:
        return wishes

    wishes.anywhere = bool(_ANYWHERE.search(text))
    wishes.big_city = bool(_BIG_CITY.search(text))
    size = _SIZE.search(text)
    if size:
        wishes.sizes = {g.upper() for g in size.groups() if g}
        text = text.replace(size.group(0), " ")
    drive = _DRIVE.search(text)
    if drive:
        wishes.drive_hours = int(drive.group(1))
    text = _blank("south bend", text)

    for club, (_, lat, lon, _) in CLUBS.items():
        names = [club] + [part.strip() for part in club.split("/") if len(part.strip()) >= 4]
        for name in names:
            if _find(name, text) and name not in STATES:
                wishes.clubs.add(club)
                wishes.places.append((club, lat, lon))
                break
    for city in sorted(CITIES, key=len, reverse=True):
        if _find(city, text) or _find_close(city, text):
            lat, lon = CITIES[city]
            if city not in wishes.clubs and all((la, lo) != (lat, lon) for _, la, lo in wishes.places):
                wishes.places.append((city, lat, lon))
            if CLUBS.get(city) and city not in wishes.clubs:
                wishes.clubs.add(city)
            text = _blank(city, text)
    for club in wishes.clubs:
        text = _blank(club, text)
    text = _drop_qualifiers(text)
    for name in sorted(STATES, key=len, reverse=True):
        if _find(name, text):
            wishes.states.add(STATES[name])
            text = _blank(name, text)
    for abbr, code in STATE_ABBREVIATIONS.items():
        if re.search(rf"(?:^|[\s,;(]){abbr}(?=$|[\s,;).])", text):
            wishes.states.add(code)
    for region, states in REGIONS.items():
        if _find(region, text):
            wishes.regions.append((region.title() if region != "canadian" else "Canada", states))
    return wishes


# ------------------------------------------------------------------ scoring

def club_location(name: str):
    """(state, lat, lon, metro size) or None."""
    key = clean(name)
    if key in CLUBS:
        return CLUBS[key]
    for state, code in STATES.items():
        if _find(state, key):
            return (code, None, None, 1)
    return None


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (lat1, lon1), (lat2, lon2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def travel_fit(answer: str, club_name: str, club_size: str = "", club_region: str = "") -> tuple[float, str]:
    """How well this club suits the professor's travel wishes: (-1..1, reason)."""
    wishes = read_wishes(answer)
    if not wishes.stated:
        return 0.0, ""
    loc = club_location(club_name)
    state, lat, lon, metro = loc if loc else (None, None, None, None)
    point = (lat, lon) if lat is not None else None
    good: list[tuple[float, str]] = []
    bad: list[tuple[float, str]] = []

    if clean(club_name) in wishes.clubs:
        good.append((1.0, f"asked for {club_name} by name"))
    if point and wishes.places:
        dist, label = min((km(point, (la, lo)), label) for label, la, lo in wishes.places)
        if dist <= NEAR_KM:
            good.append((0.85, f"near {label.title()}, which they asked for"))
        elif dist <= SHORT_TRIP_KM:
            good.append((0.6, f"a short trip from {label.title()}, which they asked for"))
    if state and state in wishes.states:
        good.append((0.7, f"in {STATE_NAMES.get(state, state)}, which they asked for"))
    for label, states in wishes.regions:
        if state in states or (not loc and club_region and clean(club_region) == clean(label)):
            good.append((0.5, f"in the {label}, which they asked for"))
    if wishes.drive_hours and point:
        if km(point, SOUTH_BEND) <= wishes.drive_hours * DRIVE_KM_PER_HOUR:
            good.append((0.6, f"within the {wishes.drive_hours}-hour drive from South Bend they asked for"))
        else:
            bad.append((-0.6, f"beyond the {wishes.drive_hours}-hour drive from South Bend they asked for"))
    if wishes.big_city and metro:
        if metro == 3:
            good.append((0.5, "a major metro, which they prefer"))
        elif metro == 1:
            bad.append((-0.6, "a smaller city, but they prefer major cities"))
    if wishes.sizes:
        if club_size in wishes.sizes:
            good.append((0.5, f"a size {club_size} club, which they prefer"))
        else:
            bad.append((-0.3, f"smaller than the {'/'.join(sorted(wishes.sizes))} clubs they prefer"))

    if good:
        return max(good)
    if bad and not wishes.anywhere:
        return min(bad)
    return 0.0, ""
