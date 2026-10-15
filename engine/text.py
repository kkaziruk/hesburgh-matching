"""Small, forgiving text helpers: months, names, titles, quotes.

Spreadsheet text is messy (curly quotes, double spaces, "Fr." and "C.S.C.",
typos). Everything here turns that mess into stable keys that compare cleanly.
"""
from __future__ import annotations

import difflib
import re

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
_MONTH_NUMBER = {m.lower(): i for i, m in enumerate(MONTHS)}

# "Some Title- January-May, September-December" -> title, months
_TITLE_THEN_MONTHS = re.compile(rf"^(.*?)\s*-\s*((?:{'|'.join(MONTHS)}).*)$", re.IGNORECASE | re.DOTALL)

_TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                             "–": "-", "—": "-", " ": " "})


def clean(s: str | None) -> str:
    """Straight quotes, plain dashes, single spaces, casefolded."""
    return re.sub(r"\s+", " ", (s or "").translate(_TYPOGRAPHY)).strip().casefold()


def tidy(s: str | None) -> str:
    """Single spaces, original case. For names shown to people."""
    return re.sub(r"\s+", " ", s or "").strip()


def name_key(name: str | None) -> str:
    """'Fr. Paul Kollman, C.S.C.' and 'paul kollman csc' -> 'paul kollman'."""
    s = clean(name)
    s = re.sub(r"\b(fr|father|rev|dr|sr|br)\.?\s+", "", s)
    s = re.sub(r",?\s*c\.?\s*s\.?\s*c\.?$", "", s)
    s = re.sub(r"[.']", "", s)
    s = re.sub(r"[-,]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_similarity(a: str, b: str) -> float:
    ka, kb = name_key(a), name_key(b)
    if not ka or not kb:
        return 0.0
    return 1.0 if ka == kb else difflib.SequenceMatcher(None, ka, kb).ratio()


def same_person(a: str, b: str, threshold: float = 0.85) -> bool:
    """Tolerates one or two typos: 'Margaret Pfiel' is 'Margaret Pfeil'."""
    return name_similarity(a, b) >= threshold


def parse_months(raw: str | None) -> list[str]:
    """'January-May, September-December', 'March,April' or 'All of the above',
    returned in calendar order. Ranges may wrap ('November-February')."""
    text = clean(raw)
    if not text:
        return []
    if "all of the above" in text or text.replace(" ", "") == "january-december":
        return MONTHS.copy()
    found: set[int] = set()
    for part in re.split(r"[,;/]", text):
        ends = [e.strip() for e in part.split("-")]
        numbers = [_MONTH_NUMBER[e] for e in ends if e in _MONTH_NUMBER]
        if len(ends) == 2 and len(numbers) == 2:
            start, stop = numbers
            span = range(start, stop + 1) if start <= stop else [*range(start, 12), *range(0, stop + 1)]
            found.update(span)
        else:
            found.update(numbers)
    return [MONTHS[i] for i in sorted(found)]


def split_request(cell: str | None) -> tuple[str | None, str | None]:
    """'Theme | Title- months' -> (theme, title).

    Splits on the '- <Month>' suffix rather than the first hyphen, so titles like
    'Leading People in an Ever-Changing World' stay whole."""
    if not cell or "|" not in cell:
        return None, None
    theme, rest = (part.strip() for part in cell.split("|", 1))
    match = _TITLE_THEN_MONTHS.match(rest)
    title = match.group(1).strip() if match else rest
    return theme or None, title or None


def ordinal(n: int | None) -> str:
    if n is None:
        return "?"
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")
