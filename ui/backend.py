"""
Bridge between the Streamlit app and the matching logic.

If the Matching engine module (/mnt/project-files/engine) is importable, it is
used. Until then, a stand-in built on the existing classes.py / parse_csv.py
produces the three plans so the interface can be built and demoed.

Everything the app needs comes back as plain pandas DataFrames / dicts:

    run(club_file, prof_file, lecture_file) -> Result
        Result.issues   DataFrame[severity, kind, subject, message]
        Result.plans    {plan_key: Plan}
        Result.source   "engine" | "stand-in"
    Plan.label, Plan.blurb, Plan.matches (DataFrame), Plan.unmatched (DataFrame),
    Plan.summary (dict)
"""
from __future__ import annotations

import difflib
import io
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PLAN_INFO = {
    "best_fit": ("Best fit", "Highest total match quality across all clubs."),
    "most_clubs": ("Most clubs served", "Matches as many clubs as possible, then maximizes quality."),
    "balanced": ("Balanced", "Spreads events across faculty and avoids repeat speakers."),
}


@dataclass
class Plan:
    key: str
    label: str
    blurb: str
    matches: pd.DataFrame
    unmatched: pd.DataFrame
    summary: dict = field(default_factory=dict)


@dataclass
class Result:
    plans: dict
    issues: pd.DataFrame
    source: str
    n_clubs: int = 0
    n_profs: int = 0


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

def _to_path(f, tmpdir: str, name: str) -> str:
    """Accept a path or a file-like upload; return a path on disk."""
    if f is None:
        raise ValueError(f"{name} is missing")
    if isinstance(f, (str, os.PathLike)):
        return str(f)
    data = f.getvalue() if hasattr(f, "getvalue") else f.read()
    p = Path(tmpdir) / name
    p.write_bytes(data)
    return str(p)


ENGINE_ERROR = None


def engine_available() -> bool:
    """True when the upgraded engine imports cleanly. A broken engine is reported, not hidden."""
    global ENGINE_ERROR
    try:
        import engine
        ENGINE_ERROR = None
        return all(hasattr(engine, n) for n in ("load_inputs", "data_issues", "run_plans"))
    except Exception as e:
        ENGINE_ERROR = None if isinstance(e, ModuleNotFoundError) and e.name == "engine" else repr(e)
        return False


def columns_supported() -> bool:
    """True when the engine lets staff choose which column holds each field."""
    if not engine_available():
        return False
    import engine
    return hasattr(engine, "COLUMN_SPEC") and hasattr(engine, "detect_columns")


def column_spec() -> dict:
    import engine
    return engine.COLUMN_SPEC


def detect_columns(club_file, prof_file, lecture_file, columns: dict | None = None) -> dict:
    """{"club": {"headers": [...], "mapping": {field: header | [headers] | None}}, ...}"""
    import engine
    return engine.detect_columns(_rewind(club_file), _rewind(prof_file), _rewind(lecture_file),
                                 columns=columns or None)


def run(club_file, prof_file, lecture_file, weights: dict | None = None, columns: dict | None = None) -> Result:
    if engine_available():
        import engine
        return _run_engine(engine, club_file, prof_file, lecture_file, weights, columns)
    return _run_standin(club_file, prof_file, lecture_file)


# ---------------------------------------------------------------------------
# Engine adapter (filled in once engine/API.md lands)
# ---------------------------------------------------------------------------

SUMMARY_LABELS = [
    ("clubs_matched", "Clubs matched"),
    ("profs_used", "Professors used"),
    ("total_score", "Total score"),
    ("avg_score", "Average score"),
    ("top_choice_matches", "Got their 1st choice"),
    ("requested_lecture_matches", "Got a requested lecture"),
    ("repeat_speakers", "Repeat speakers"),
    ("max_events_per_prof", "Most events for one prof"),
    ("month_clashes", "Month clashes"),
    ("staff_pick_agreement", "Agrees with staff picks"),
]
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}


def _rewind(f):
    if hasattr(f, "seek"):
        f.seek(0)
    return f


def _run_engine(engine, club_file, prof_file, lecture_file, weights=None, columns=None) -> Result:
    extra = {"columns": columns} if columns and columns_supported() else {}
    data = engine.load_inputs(_rewind(club_file), _rewind(prof_file), _rewind(lecture_file), **extra)
    raw_issues = engine.data_issues(data)
    issues = pd.DataFrame(
        [(i.get("severity", ""), str(i.get("kind", "")).replace("_", " ").capitalize(),
          i.get("subject", ""), i.get("message", "")) for i in raw_issues],
        columns=["Severity", "Issue", "Who", "Details"])

    plans = {}
    for key, p in engine.run_plans(data, weights=weights or None).items():
        m = p.matches.copy()
        md = pd.DataFrame({
            "Club": m.get("club"), "Club ID": m.get("club_id"), "Region": m.get("region"),
            "Size": m.get("size"), "Engagement": m.get("engagement"),
            "Professor": m.get("professor"),
            "Title": m.get("title", pd.Series(dtype=str)).fillna("").str.title(),
            "Score": m.get("score").astype(float).round(2) if "score" in m else None,
            "Why": m.get("why"),
            "Month": m.get("suggested_month"),
            "Choice": m.get("choice_rank").map(lambda v: ORDINAL.get(int(v), "") if pd.notna(v) else "") if "choice_rank" in m else "",
            "Repeat speaker": m.get("repeat_speaker", False).astype(bool) if "repeat_speaker" in m else False,
            "Prof events": [f"{a} of {b}" for a, b in zip(m.get("prof_events", []), m.get("prof_max_events", []))] if len(m) else [],
            "Staff pick": m.get("staff_pick"),
            "Shared lectures": m.get("shared_lectures"), "Shared themes": m.get("shared_themes"),
            "Shared months": m.get("shared_months"), "Shared formats": m.get("shared_formats"),
        }) if len(m) else pd.DataFrame(columns=["Club", "Professor", "Score", "Region"])
        if len(md):
            md = md.sort_values("Score", ascending=False)

        u = p.unmatched
        opts = []
        for _, r in u.iterrows():
            names = [str(r.get(f"suggestion_{i}") or "").strip() for i in (1, 2, 3)]
            opts.append(", ".join(n for n in names if n and n != "nan") or "—")
        ud = pd.DataFrame({
            "Club": u.get("club"), "Club ID": u.get("club_id"), "Region": u.get("region"),
            "Size": u.get("size"), "Reason": u.get("reason"), "Closest options": opts,
        }) if len(u) else pd.DataFrame(columns=["Club", "Club ID", "Region", "Size", "Reason", "Closest options"])

        s = p.summary
        summary = {label: s[k] for k, label in SUMMARY_LABELS if k in s}
        summary["Clubs total"] = s.get("clubs_total", getattr(data, "n_clubs", 0))
        summary["Professors total"] = s.get("profs_available", getattr(data, "n_profs", 0))
        if "Total score" in summary:
            summary["Total score"] = round(float(summary["Total score"]), 1)
        if "Average score" in summary:
            summary["Average score"] = round(float(summary["Average score"]), 1)
        plans[key] = Plan(key, p.label, getattr(p, "description", ""), md, ud, summary)

    return Result(plans=plans, issues=issues, source="engine",
                  n_clubs=getattr(data, "n_clubs", 0), n_profs=getattr(data, "n_profs", 0))


# ---------------------------------------------------------------------------
# Stand-in using the existing code
# ---------------------------------------------------------------------------

def _run_standin(club_file, prof_file, lecture_file) -> Result:
    legacy = ROOT / "legacy"
    if legacy.is_dir() and str(legacy) not in sys.path:
        sys.path.insert(0, str(legacy))
    from classes import Match
    from parse_csv import load_clubs_from_csv, load_profs_from_csv

    with tempfile.TemporaryDirectory() as td:
        cp = _to_path(club_file, td, "club_info.csv")
        pp = _to_path(prof_file, td, "prof_info.csv")
        lp = _to_path(lecture_file, td, "lecture_info.csv")
        clubs = load_clubs_from_csv(cp)
        profs = load_profs_from_csv(pp, lp)
        catalog = pd.read_csv(lp)

    issues = _data_issues(clubs, profs, catalog)

    pairs = {}
    for ci, c in enumerate(clubs):
        for pi, p in enumerate(profs):
            m = Match(c, p)
            if m.score > 0:
                pairs[(ci, pi)] = m

    def repeat(c, p):
        last = p.name.split()[-1].lower()
        return any(p.name.lower() == s.lower() or last in s.lower() for s in c.past_speakers)

    plans = {}
    for key in PLAN_INFO:
        chosen = _solve(key, clubs, profs, pairs, repeat)
        plans[key] = _build_plan(key, chosen, clubs, profs, pairs, repeat)
    return Result(plans=plans, issues=issues, source="stand-in", n_clubs=len(clubs), n_profs=len(profs))


def _solve(key, clubs, profs, pairs, repeat):
    """Capacity-aware assignment via the Hungarian method on professor slots."""
    from scipy.optimize import linear_sum_assignment

    slots = []  # (prof_index, slot_number starting at 1)
    for pi, p in enumerate(profs):
        for k in range(1, (p.max_events or 1) + 1):
            slots.append((pi, k))
    if not slots or not clubs:
        return []

    NEG = -1e9
    W = np.full((len(clubs), len(slots)), NEG)
    for j, (pi, k) in enumerate(slots):
        for ci, c in enumerate(clubs):
            m = pairs.get((ci, pi))
            if m is None:
                continue
            s = m.score
            if key == "most_clubs":
                s = 1000.0 + s
            elif key == "balanced":
                s = s * (1.0 - 0.35 * (k - 1))
                if repeat(c, profs[pi]):
                    s *= 0.3
            W[ci, j] = s
    rows, cols = linear_sum_assignment(-W)
    return [(r, slots[c][0]) for r, c in zip(rows, cols) if W[r, c] > NEG / 2]


def _why(m) -> str:
    bits = []
    if m.shared_lectures:
        bits.append(f"requested “{m.shared_lectures[0]}”" + (f" +{len(m.shared_lectures)-1}" if len(m.shared_lectures) > 1 else ""))
    elif m.shared_themes:
        bits.append(f"theme {', '.join(m.shared_themes)}")
    bits.append(f"{len(m.shared_months)} shared month{'s' if len(m.shared_months) != 1 else ''}")
    if m.shared_formats:
        bits.append("format fits")
    return "; ".join(bits)


def _build_plan(key, chosen, clubs, profs, pairs, repeat) -> Plan:
    label, blurb = PLAN_INFO[key]
    load = pd.Series([pi for _, pi in chosen]).value_counts().to_dict() if chosen else {}
    rows = []
    for ci, pi in sorted(chosen, key=lambda t: -pairs[t].score):
        m, c, p = pairs[(ci, pi)], clubs[ci], profs[pi]
        rows.append({
            "Club": c.name, "Club ID": c.id, "Region": c.region, "Size": c.size,
            "Engagement": c.eg_score, "Professor": p.name, "Title": p.title.title(),
            "Score": round(m.score, 2), "Why": _why(m),
            "Repeat speaker": repeat(c, p),
            "Prof events": f"{load.get(pi, 0)} of {p.max_events}",
            "Shared lectures": "; ".join(m.shared_lectures),
            "Shared themes": "; ".join(m.shared_themes),
            "Shared months": "; ".join(m.shared_months),
            "Shared formats": "; ".join(m.shared_formats),
        })
    matches = pd.DataFrame(rows)

    used = {ci for ci, _ in chosen}
    un = []
    for ci, c in enumerate(clubs):
        if ci in used:
            continue
        options = sorted(((pairs[(ci, pi)].score, profs[pi].name) for pi in range(len(profs)) if (ci, pi) in pairs), reverse=True)
        if getattr(c, "missing_availability", False):
            reason = "No availability on the club form"
        elif not options:
            reason = "No professor shares both a month and a requested topic"
        else:
            reason = "Every compatible professor was booked by another club"
        un.append({
            "Club": c.name, "Club ID": c.id, "Region": c.region, "Size": c.size,
            "Reason": reason,
            "Closest options": ", ".join(f"{n} ({s:.0f})" for s, n in options[:3]) or "—",
        })
    unmatched = pd.DataFrame(un, columns=["Club", "Club ID", "Region", "Size", "Reason", "Closest options"])

    profs_used = len(load)
    summary = {
        "Clubs matched": len(matches),
        "Clubs total": len(clubs),
        "Professors used": profs_used,
        "Professors total": len(profs),
        "Total score": round(float(matches["Score"].sum()) if len(matches) else 0.0, 1),
        "Average score": round(float(matches["Score"].mean()) if len(matches) else 0.0, 1),
        "Repeat speakers": int(matches["Repeat speaker"].sum()) if len(matches) else 0,
        "Most events for one prof": max(load.values()) if load else 0,
        "Regions covered": matches["Region"].nunique() if len(matches) else 0,
    }
    return Plan(key, label, blurb, matches, unmatched, summary)


def _data_issues(clubs, profs, catalog: pd.DataFrame) -> pd.DataFrame:
    out = []
    for c in clubs:
        if getattr(c, "missing_availability", False):
            out.append(("warning", "Missing availability", c.name, "Club has no months listed, so it can't be matched."))
        if not (c.size or "").strip():
            out.append(("warning", "Missing size", c.name, "Club size is blank."))
    fac_col = next((col for col in catalog.columns if col.strip().lower() == "faculty"), None)
    catalog_names = sorted({str(x).strip() for x in catalog[fac_col].dropna()}) if fac_col else []
    for p in profs:
        if not p.lectures:
            guess = difflib.get_close_matches(p.name, catalog_names, n=1, cutoff=0.6)
            hint = f" Closest name in the lecture list: “{guess[0]}”." if guess else ""
            out.append(("error", "Professor has no lectures", p.name,
                        f"Not found in lecture_info.csv, so this professor can't be matched.{hint}"))
        if not p.months_avail:
            out.append(("warning", "Missing availability", p.name, "Professor has no months listed."))
    return pd.DataFrame(out, columns=["Severity", "Issue", "Who", "Details"])


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def to_excel(result: Result, keys=None, settings: dict | None = None) -> bytes:
    keys = keys or list(result.plans)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        comp = comparison_table(result)
        comp.to_excel(xw, sheet_name="Comparison")
        if settings:
            pd.DataFrame(list(settings.items()), columns=["Priority", "Setting"]).to_excel(
                xw, sheet_name="Settings used", index=False)
        for k in keys:
            p = result.plans[k]
            p.matches.to_excel(xw, sheet_name=f"{p.label[:22]} matches", index=False)
            p.unmatched.to_excel(xw, sheet_name=f"{p.label[:20]} unmatched", index=False)
        if len(result.issues):
            result.issues.to_excel(xw, sheet_name="Data check", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            ws.freeze_panes = "B2" if ws.title == "Comparison" else "A2"
    return buf.getvalue()


def comparison_table(result: Result) -> pd.DataFrame:
    return pd.DataFrame({p.label: p.summary for p in result.plans.values()})
