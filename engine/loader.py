"""Read the three CSV exports into clean objects, and say what was wrong with them.

Nothing here raises on messy data. Columns are found by meaning (see
columns.py), so added, reordered or slightly renamed columns are fine. Every
repair, skipped row or missing column becomes an issue staff can read, so no
data disappears silently.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from .columns import FILES, Columns, fields_for, resolve
from .model import Club, Lecture, MatchData, Professor, Request
from .scoring import TITLE_BOOST
from .text import MONTHS, clean, name_key, name_similarity, parse_months, split_request, tidy

SIZE_CODES = ("AA", "A", "B", "C", "D", "E", "F")


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
BYTE_ORDER_MARK = chr(0xFEFF)


class Issues(list):
    """A list of {severity, kind, subject, message} that ignores exact repeats."""

    def add(self, severity: str, kind: str, subject: str, message: str) -> None:
        item = {"severity": severity, "kind": kind, "subject": subject, "message": message}
        if item not in self:
            self.append(item)

    def error(self, kind, subject, message):
        self.add("error", kind, subject, message)

    def warn(self, kind, subject, message):
        self.add("warning", kind, subject, message)

    def note(self, kind, subject, message):
        self.add("info", kind, subject, message)


# ------------------------------------------------------------------ reading

def read_table(source) -> tuple[list[str], list[dict[str, str]]]:
    """A path or an uploaded file (bytes or text) -> (headers, rows keyed by trimmed header)."""
    if isinstance(source, (str, Path)):
        raw = Path(source).read_bytes()
    else:
        if hasattr(source, "seek"):
            source.seek(0)
        raw = source.getvalue() if hasattr(source, "getvalue") else source.read()
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raw = raw.decode("cp1252")          # Excel on Windows
    reader = csv.DictReader(io.StringIO(raw.lstrip(BYTE_ORDER_MARK), newline=""))
    headers = [(h or "").strip() for h in reader.fieldnames or []]
    rows = [{(k or "").strip(): (v or "") for k, v in row.items() if k is not None} for row in reader]
    return headers, rows


def first_number(text: str) -> int | None:
    found = re.search(r"\d+", text or "")
    return int(found.group()) if found else None


def split_list(text: str) -> list[str]:
    return [item.strip() for item in (text or "").split(",") if item.strip()]


def senior_title(raw: str) -> str:
    """The most senior title in a long job description.

    Longer titles are matched first and blanked out, so "Associate Provost" is not
    also read as "Provost". "Vice President and Associate Provost" -> "vice president"."""
    text, held = clean(raw), []
    for title in sorted(TITLE_BOOST, key=len, reverse=True):
        if title in text:
            held.append(title)
            text = text.replace(title, " ")
    return max(held, key=lambda t: TITLE_BOOST[t], default="professor")


# ------------------------------------------------------------------ lectures

def load_lectures(rows, col: Columns, issues: Issues) -> list[Lecture]:
    lectures, seen = [], set()
    for row in rows:
        faculty, theme, topic = (col.get(row, key).strip() for key in ("faculty", "theme", "topic"))
        if not (faculty and theme and topic):
            if any(v.strip() for v in row.values()):
                issues.warn("dropped_row", faculty or topic or "lecture_info.csv",
                            "Lecture row skipped because Faculty, Theme or Topic is blank.")
            continue
        key = (name_key(faculty), clean(theme), clean(topic))
        if key not in seen:                     # the catalog lists some lectures twice
            seen.add(key)
            months = parse_months(col.get(row, "availability")) or MONTHS.copy()
            lectures.append(Lecture(theme, topic, months, faculty))
    return lectures


def attach_lectures(profs: list[Professor], lectures: list[Lecture], issues: Issues) -> None:
    """Give each lecture to the professor whose name it (nearly) carries."""
    for lecture in lectures:
        owner = max(profs, key=lambda p: name_similarity(p.name, lecture.listed_under), default=None)
        similarity = name_similarity(owner.name, lecture.listed_under) if owner else 0.0
        if similarity < 0.85:
            issues.warn("lecture_not_found", lecture.listed_under,
                        f"Lecture '{lecture.title}' belongs to '{lecture.listed_under}', "
                        "who is not in prof_info.csv.")
            continue
        if similarity < 1.0:
            issues.warn("name_mismatch", owner.name,
                        f"Catalog lists this professor as '{lecture.listed_under}'; matched automatically.")
        owner.lectures.append(lecture)

    for prof in profs:
        if not prof.lectures:
            issues.error("prof_no_lectures", prof.name,
                         "No lectures found in lecture_info.csv for this professor, "
                         "so they can never be matched.")


# ------------------------------------------------------------------ professors

def is_survey_label_row(name: str, header: str) -> bool:
    """Raw Qualtrics exports carry a second header row; this file usually does not."""
    return name.lower() in {"recipient full name", header.lower()} or name.startswith("{")


def load_profs(rows, col: Columns, issues: Issues) -> list[Professor]:
    profs = []
    for number, row in enumerate(rows, start=2):           # row 1 is the header
        name = tidy(col.get(row, "name"))
        if number == 2 and is_survey_label_row(name, col.found["name"]):
            issues.note("dropped_row", "prof_info.csv row 2", "Dropped a survey label row (not a professor).")
            continue
        if not name:
            if any(v.strip() for v in row.values()):
                issues.warn("dropped_row", f"prof_info.csv row {number}",
                            "Professor row skipped because the name is blank.")
            continue
        if col.get(row, "participate").strip().lower().startswith("no"):
            issues.note("declined", name, "Declined to participate in 2026; not matched.")
            continue

        months = parse_months(col.get(row, "availability"))
        if not months:
            issues.warn("missing_availability", name, "No availability months, so this professor cannot be matched.")

        max_events = first_number(col.get(row, "max_events"))
        if max_events is None and col.has("max_events"):
            issues.warn("blank_score", name, "# of Events is blank; assuming 1.")

        title_raw = col.get(row, "title").strip()
        if title_raw and not any(t in clean(title_raw) for t in TITLE_BOOST):
            issues.note("unknown_title", name,
                        f"Title '{title_raw.splitlines()[0]}' not recognised; treated as professor.")

        profs.append(Professor(
            name=name,
            title=senior_title(title_raw),
            title_raw=title_raw,
            months=months,
            max_events=max(1, max_events or 1),
            formats=split_list(col.get(row, "formats")),
            travel_wishes=col.get(row, "travel"),
        ))
    return profs


# ------------------------------------------------------------------ clubs

def is_in_program(row: dict, col: Columns) -> bool:
    """Invited this year, or sent in at least one request."""
    themes = col.get_all(row, "themes")
    return col.get(row, "invited").strip().lower() == "invited" or bool(themes and themes[0].strip())


def read_requests(row: dict, col: Columns, catalog: set[str], club: str, issues: Issues) -> list[Request]:
    requests, seen = [], set()
    for rank, cell in enumerate(col.get_all(row, "themes"), start=1):
        theme, title = split_request(cell)
        key = (clean(theme), clean(title))
        if not (theme or title) or key in seen:
            continue
        seen.add(key)
        requests.append(Request(rank, theme, title))
        if title and clean(title) not in catalog:
            issues.warn("lecture_not_found", club, f"Requested lecture '{title}' is not in lecture_info.csv.")
    return requests


def load_clubs(rows, col: Columns, lectures: list[Lecture], issues: Issues) -> list[Club]:
    catalog = {clean(lec.title) for lec in lectures}
    clubs = []
    for row in (r for r in rows if is_in_program(r, col)):
        club_id, name = col.get(row, "id").strip(), col.get(row, "name").strip()
        if not (club_id and name):
            issues.warn("dropped_row", name or club_id or "club_info.csv",
                        "Club row skipped because the ID or club name is blank.")
            continue

        size = col.get(row, "size").strip().upper()
        if size not in SIZE_CODES and col.has("size"):
            issues.warn("blank_size", name, f"Size '{size}' is not AA-F; using a middle value." if size
                        else "Size is blank; using a middle value.")
        if size not in SIZE_CODES:
            size = ""

        engagement = first_number(col.get(row, "hls_score").replace(",", ""))
        if engagement is None and col.has("hls_score"):
            issues.warn("blank_score", name, "HLS Score is blank; using a middle value.")

        months = parse_months(col.get(row, "availability"))
        requests = read_requests(row, col, catalog, name, issues)
        if not (requests or months):
            issues.warn("missing_availability", name, "No request form: Availability and Theme 1-5 are blank.")
        elif not months:
            issues.warn("missing_availability", name, "Availability is blank.")
        elif not requests:
            issues.warn("missing_availability", name, "No themes or lectures requested.")

        past = (p.strip() for p in col.get_all(row, "past_speakers"))
        clubs.append(Club(
            id=club_id, name=name, size=size, region=col.get(row, "region").strip(),
            engagement=engagement, months=months, formats=split_list(col.get(row, "format")),
            requests=requests, past_speakers=[p for p in past if p],
            staff_pick=tidy(col.get(row, "staff_pick")),
        ))
    return clubs


# ------------------------------------------------------------------ public

def _read_all(club_csv, prof_csv, lecture_csv, columns, issues) -> dict[str, tuple[Columns, list[dict]]]:
    tables = {}
    for group, source in (("club", club_csv), ("prof", prof_csv), ("lecture", lecture_csv)):
        headers, rows = read_table(source)
        if not rows:
            issues.error("empty_file", FILES[group], f"{FILES[group]} has no data rows.")
        tables[group] = (resolve(group, headers, (columns or {}).get(group), issues), rows)
    return tables


def _rows_if_usable(col: Columns, rows: list[dict]) -> list[dict]:
    """A file missing a required column has already been reported; skip its rows."""
    return rows if all(col.has(f.key) for f in fields_for(col.file) if f.required) else []


def detect_columns(club_csv, prof_csv, lecture_csv, columns=None) -> dict:
    """Which header the engine will use for each field, without loading anything.

    Returns {"club": {"headers": [...], "mapping": {field: header | [headers] | None}}, "prof": ..., "lecture": ...}."""
    tables = _read_all(club_csv, prof_csv, lecture_csv, columns, Issues())
    return {group: {"headers": col.headers, "mapping": dict(col.found)} for group, (col, _) in tables.items()}


def load_inputs(club_csv, prof_csv, lecture_csv, columns=None) -> MatchData:
    """Read the three exports (paths or uploaded files) into one MatchData.

    `columns` optionally overrides where fields live, using the keys in COLUMN_SPEC:
    {"club": {"size": "Club Size", "themes": ["Pick 1", "Pick 2"]}, "prof": {...}}."""
    issues = Issues()
    tables = _read_all(club_csv, prof_csv, lecture_csv, columns, issues)
    (club_col, club_rows), (prof_col, prof_rows), (lec_col, lec_rows) = tables.values()

    lectures = load_lectures(_rows_if_usable(lec_col, lec_rows), lec_col, issues)
    profs = load_profs(_rows_if_usable(prof_col, prof_rows), prof_col, issues)
    attach_lectures(profs, lectures, issues)
    clubs = load_clubs(_rows_if_usable(club_col, club_rows), club_col, lectures, issues)
    return MatchData(clubs, profs, lectures, issues,
                     columns={group: dict(col.found) for group, (col, _) in tables.items()})


def data_issues(data: MatchData) -> list[dict]:
    """Everything staff should know about the inputs, most serious first."""
    return sorted(data.issues, key=lambda i: (SEVERITY_ORDER.get(i["severity"], 9), i["kind"], i["subject"]))
