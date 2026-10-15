"""Find each piece of information in a spreadsheet by what it means, not where it sits.

Every input the engine reads is a `Field` in `SCHEMA`: a stable key, the header
the exports use today, a few other names it might go by, and whether matching
can work without it. For each field, `resolve` looks through the actual headers
in this order:

  1. a header the user chose explicitly (an override from the app or a JSON file);
  2. the usual header or a known alternative, ignoring case, spaces and punctuation
     ("HLS Score", "hls_score" and "HLS score " are the same);
  3. a pattern, for families of columns: "Theme 1".."Theme 7", "2022 Speaker".."2026 Speaker",
     and year-stamped columns such as "Invited 2027" (the latest year wins);
  4. a close spelling ("Availabilty"), as a last resort.

Columns nobody asks for are ignored, so adding or reordering columns never breaks anything.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

FILES = {"club": "club_info.csv", "prof": "prof_info.csv", "lecture": "lecture_info.csv"}


@dataclass(frozen=True)
class Field:
    file: str                 # "club", "prof" or "lecture"
    key: str                  # stable name the code uses
    header: str               # what the export calls it today
    meaning: str              # one line for staff
    required: bool = False
    also: tuple[str, ...] = ()
    pattern: str | None = None   # regex on the normalised header; group 1 is a number used for ordering
    many: bool = False           # a family of columns (Theme 1-5) rather than one
    newest_first: bool = False   # order a family by descending number (years)


SCHEMA: list[Field] = [
    # ------------------------------------------------------------ club_info.csv
    Field("club", "id", "ID Number", "Unique club ID", True, ("Club ID", "ID")),
    Field("club", "name", "Club Check", "Club name", True, ("Club", "Club Name")),
    Field("club", "availability", "Availability", "Months the club can host, comma-separated", True,
          ("Months", "Available Months")),
    Field("club", "themes", "Theme 1 … Theme 5", "The club's ranked requests, 'Theme | Lecture- months'", True,
          pattern=r"^theme(\d+)$", many=True),
    Field("club", "size", "Size", "Club size code AA … F", also=("Club Size",)),
    Field("club", "hls_score", "HLS Score", "Engagement score", also=("Engagement Score", "Engagement")),
    Field("club", "region", "Region", "Region name"),
    Field("club", "format", "Format", "Talk formats the club wants, comma-separated", also=("Formats", "Format(s)")),
    Field("club", "invited", "Invited 2026", "'Invited' marks a club in this year's program",
          pattern=r"^invited(\d{4})?$", newest_first=True),
    Field("club", "past_speakers", "2025 Speaker … 2022 Speaker", "Speakers from earlier years",
          pattern=r"^(\d{4})speaker$", many=True, newest_first=True),
    Field("club", "staff_pick", "2026 Assignment", "Staff's own pick, used only for comparison",
          pattern=r"^(\d{4})assignment$", newest_first=True),

    # ------------------------------------------------------------ prof_info.csv
    Field("prof", "name", "Recipient Full Name", "Professor's full name", True,
          ("Full Name", "Name", "Professor", "Faculty")),
    Field("prof", "availability", "Availability", "Months available, or 'All of the above'", True,
          ("Months", "Available Months")),
    Field("prof", "max_events", "# of Events", "Most events this professor will do (blank = 1)",
          also=("Number of Events", "Max Events", "Events")),
    Field("prof", "title", "Title", "Job title, for the title boost", also=("Job Title", "Position")),
    Field("prof", "formats", "Format(s)", "Talk formats offered, comma-separated", also=("Formats", "Format")),
    Field("prof", "participate", "Participate in the Hesburgh Lecture program in 2026?",
          "Answers starting 'No' are skipped", pattern=r"^participate"),
    Field("prof", "travel", "Particular clubs or areas of the country you are interested in traveling?",
          "Free-text travel wishes, for the Balanced plan", pattern=r"^particularclubs|areasofthecountry|travelpref"),

    # ------------------------------------------------------------ lecture_info.csv
    Field("lecture", "faculty", "Faculty", "Professor who gives the lecture", True, ("Professor", "Speaker", "Name")),
    Field("lecture", "theme", "Theme", "Theme the lecture belongs to", True, ("Category",)),
    Field("lecture", "topic", "Topic", "Lecture title, spelled as clubs request it", True,
          ("Title", "Lecture", "Lecture Title")),
    Field("lecture", "availability", "Availability", "Months the lecture is offered (blank = all year)",
          also=("Months",)),
]


def fields_for(file: str) -> list[Field]:
    return [f for f in SCHEMA if f.file == file]


def squash(header: str) -> str:
    """'HLS Score ' -> 'hlsscore'; '# of Events' -> 'ofevents'."""
    return re.sub(r"[^a-z0-9]", "", (header or "").casefold())


@dataclass
class Columns:
    """Where each field lives in one file: {key: header} or {key: [headers]}."""
    file: str
    headers: list[str]
    found: dict

    def get(self, row: dict, key: str) -> str:
        header = self.found.get(key)
        return row.get(header, "") if isinstance(header, str) else ""

    def get_all(self, row: dict, key: str) -> list[str]:
        return [row.get(h, "") for h in self.found.get(key) or []]

    def has(self, key: str) -> bool:
        return bool(self.found.get(key))


def resolve(file: str, headers: list[str], overrides: dict | None, issues) -> Columns:
    """Decide which header holds each field, reporting anything unusual."""
    overrides = overrides or {}
    squashed = {squash(h): h for h in headers}
    taken: set[str] = set()
    found: dict = {}
    fname = FILES[file]

    # Explicit choices first, so automatic matching never steals their columns.
    for field in fields_for(file):
        if field.key not in overrides or overrides[field.key] in (None, "", []):
            continue
        wanted = overrides[field.key]
        wanted = list(wanted) if field.many and not isinstance(wanted, str) else wanted
        names = wanted if isinstance(wanted, list) else [wanted]
        missing = [n for n in names if n not in headers]
        if missing:
            issues.error("missing_column", fname,
                         f"Column '{missing[0]}' chosen for '{field.header}' is not in {fname}.")
            continue
        found[field.key] = names if field.many else names[0]
        taken.update(names)

    for field in fields_for(file):
        if field.key in found:
            continue
        match = _automatic(field, headers, squashed, taken)
        if match:
            found[field.key] = match
            taken.update(match if isinstance(match, list) else [match])
            first = match[0] if isinstance(match, list) else match
            if not field.many and not field.pattern and squash(first) not in {squash(field.header), *map(squash, field.also)}:
                issues.note("column_matched", fname, f"Using column '{first}' for '{field.header}'.")
        elif field.required:
            issues.error("missing_column", fname,
                         f"Required column '{field.header}' ({field.meaning.lower()}) was not found. "
                         "Rename it back or choose the column in Settings.")
        else:
            found[field.key] = [] if field.many else None
            issues.note("missing_column", fname,
                        f"Optional column '{field.header}' not found ({field.meaning.lower()}); "
                        "matching works without it.")
    return Columns(file, headers, found)


def _automatic(field: Field, headers, squashed, taken):
    free = lambda h: h not in taken
    if not field.many:
        for name in (field.header, *field.also):
            h = squashed.get(squash(name))
            if h and free(h):
                return h
    if field.pattern:
        hits = []
        for h in headers:
            m = re.search(field.pattern, squash(h))
            if m and free(h):
                number = int(m.group(1)) if m.groups() and m.group(1) else 0
                hits.append((number, h))
        if hits:
            hits.sort(key=lambda t: t[0], reverse=field.newest_first)
            return [h for _, h in hits] if field.many else hits[0][1]
    if not field.many:
        candidates = [h for h in headers if free(h)]
        close = difflib.get_close_matches(squash(field.header), [squash(h) for h in candidates], n=1, cutoff=0.88)
        if close:
            return next(h for h in candidates if squash(h) == close[0])
    return [] if field.many else None


def _label(field: Field) -> str:
    return field.header if not field.many else field.header.replace(" … ", " to ")


def _defaults(field: Field) -> list[str]:
    """The header(s) today's exports use."""
    if field.key == "themes":
        return [f"Theme {i}" for i in range(1, 6)]
    if field.key == "past_speakers":
        return [f"{y} Speaker" for y in (2025, 2024, 2023, 2022)]
    return [field.header]


COLUMN_SPEC = {
    group: [{"field": f.key, "label": _label(f), "required": f.required, "multi": f.many,
             "default": _defaults(f), "meaning": f.meaning} for f in fields_for(group)]
    for group in FILES
}
