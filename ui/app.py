"""
Hesburgh Lecture Matching: staff app.

Run locally:   streamlit run ui/app.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

import backend

ROOT = Path(__file__).resolve().parent.parent
GOLD = "#C99700"
NAVY = "#0C2340"
INK = "#1B1B1B"
PAPER = "#F3F2EE"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

st.set_page_config(page_title="Hesburgh Lecture Matching", page_icon="🎓", layout="wide",
                   initial_sidebar_state="collapsed")

# ============================================================================ Priorities model
# Each priority is shown as five plain-language levels instead of raw numbers.
LEVELS = ["Off", "Low", "Standard", "High", "Max"]
PRIORITIES = [
    # key, label, help, values per level, group
    ("size", "Club size", "Bigger clubs get first call on the strongest matches.",
     [0, 0.5, 1, 1.5, 2], "all"),
    ("engagement", "Club engagement", "Clubs with a higher HLS engagement score get priority.",
     [0, 0.5, 1, 1.5, 2], "all"),
    ("choice_rank", "Clubs' ranked choices", "How much a club's 1st choice beats its 5th.",
     [0, 0.5, 1, 1.5, 2], "all"),
    ("title", "Speaker seniority", "Boost for deans, provosts and directors.",
     [0, 0.5, 1, 1.5, 2], "all"),
    ("repeat_penalty", "Avoid repeat speakers", "Steer away from speakers a club hosted in 2022–2025.",
     [0, 0.5, 1, 2, 3], "balanced"),
    ("spread", "Spread across faculty", "Discourage stacking several events on one professor.",
     [0, 0.5, 1, 2, 3], "balanced"),
    ("travel_bonus", "Professors' travel wishes", "Favour clubs in areas professors said they'd like to visit.",
     [0, 0.5, 1, 2, 3], "balanced"),
]
PKEYS = [p[0] for p in PRIORITIES]
STANDARD = {k: "Standard" for k in PKEYS}
PRESETS = {
    "Standard": {},
    "Bigger clubs first": {"size": "Max", "engagement": "Low"},
    "Most engaged clubs": {"engagement": "Max", "size": "Low"},
    "Clubs' wishes first": {"choice_rank": "Max", "title": "Low"},
    "Share the faculty": {"spread": "Max", "repeat_penalty": "High", "travel_bonus": "High"},
    "No seniority boost": {"title": "Off"},
}
LEGACY_KEYS = {"size_weight": "size", "eng_weight": "engagement", "title_weight": "title"}


def preset_levels(name):
    return {**STANDARD, **PRESETS[name]}


def levels_to_weights(levels):
    return {k: vals[LEVELS.index(levels[k])] for k, _, _, vals, _ in PRIORITIES}


def weights_to_levels(w):
    out = {}
    for k, _, _, vals, _ in PRIORITIES:
        v = float(w.get(k, 1.0))
        out[k] = LEVELS[min(range(len(vals)), key=lambda i: abs(vals[i] - v))]
    return out


def current_levels():
    return {k: st.session_state.get(f"lvl_{k}", "Standard") for k in PKEYS}


def matching_preset(levels):
    return next((n for n in PRESETS if preset_levels(n) == levels), None)


# ---- widget callbacks (run before the page redraws, so state stays consistent)
def on_preset():
    name = st.session_state.get("preset")
    if name:
        for k, v in preset_levels(name).items():
            st.session_state[f"lvl_{k}"] = v


def on_slider():
    st.session_state["preset"] = matching_preset(current_levels())


def on_reset():
    st.session_state["preset"] = "Standard"
    on_preset()


def on_settings_upload():
    f = st.session_state.get("settings_file")
    if not f:
        return
    try:
        doc = json.loads(f.getvalue().decode("utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("not a settings file")
        if "weights" in doc or "columns" in doc:
            raw_w, raw_c = doc.get("weights") or {}, doc.get("columns") or {}
        else:  # an old weights.json
            raw_w, raw_c = doc, {}
        raw_w = {LEGACY_KEYS.get(a, a): float(b) for a, b in raw_w.items()
                 if isinstance(b, (int, float)) and LEGACY_KEYS.get(a, a) in PKEYS}
        for k, v in weights_to_levels({**levels_to_weights(STANDARD), **raw_w}).items():
            st.session_state[f"lvl_{k}"] = v
        st.session_state["preset"] = matching_preset(current_levels())
        if isinstance(raw_c, dict):
            st.session_state["colmap"] = {s: dict(m) for s, m in raw_c.items() if isinstance(m, dict)}
        st.session_state["settings_msg"] = ("ok", f"Loaded settings from {f.name}.")
    except Exception:
        st.session_state["settings_msg"] = ("err", f"{f.name} isn't a settings file saved from this app.")


if "preset" not in st.session_state:
    st.session_state["preset"] = "Standard"
    on_preset()

# ============================================================================ Styles
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
  .stApp, .stApp :is(p, label, input, textarea, button, li, td, th, div) {{
      font-family: 'Inter', system-ui, sans-serif; }}
  [data-testid="stAppViewContainer"] {{ background: {PAPER}; }}
  [data-testid="stHeader"], [data-testid="stSidebarCollapsedControl"], [data-testid="stToolbar"] {{ display: none; }}
  .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1320px; }}

  /* top bar */
  .topbar {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
             padding: .2rem 0 .9rem 0; border-bottom: 1px solid #1b1b1b1f; margin-bottom: .2rem; }}
  .brand {{ display: flex; align-items: baseline; gap: .7rem; flex-wrap: wrap; }}
  .brand .mark {{ font-family: 'Instrument Serif', serif !important; font-size: 1.9rem; line-height: 1; color: {INK}; }}
  .brand .mark i {{ color: {GOLD}; font-style: italic; }}
  .brand .tag {{ font-family: 'JetBrains Mono', monospace !important; font-size: .75rem; color: #6b675d; }}
  .status {{ display: flex; flex-wrap: wrap; gap: .4rem; justify-content: flex-end; }}
  .pill {{ font-family: 'JetBrains Mono', monospace !important; font-size: .74rem; border: 1px solid #1b1b1b26;
           border-radius: 99px; padding: .18rem .65rem; background: #fffdf8; color: {INK}; white-space: nowrap; }}
  .pill.err {{ background: #fdecea; border-color: #e9b4ae; color: #8c1d18; }}
  .pill.warn {{ background: #fff4d6; border-color: #e8d29a; color: #6b5200; }}
  .pill.ok {{ background: #e7f2ea; border-color: #b6d8c0; color: #1e5b33; }}

  /* main tabs styled as a numbered nav */
  div[data-testid="stTabs"] div[role="tablist"] {{ gap: 1.6rem; }}
  div[data-testid="stTabs"] button[role="tab"] p {{ font-family: 'JetBrains Mono', monospace !important;
           font-size: .86rem; letter-spacing: .01em; color: #6b675d; }}
  div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p {{ color: {INK}; font-weight: 600; }}
  div[data-baseweb="tab-highlight"] {{ background-color: {INK}; }}

  /* section headers */
  .kicker {{ font-family: 'JetBrains Mono', monospace !important; font-size: .75rem; color: #8a8576;
             letter-spacing: .06em; text-transform: uppercase; margin: 1.1rem 0 .15rem 0; }}
  .h {{ font-family: 'Instrument Serif', serif !important; font-size: 2.3rem; line-height: 1.05; color: {INK};
        margin: 0 0 .35rem 0; }}
  .h i {{ color: {GOLD}; }}
  .lead {{ color: #4a473f; font-size: 1.0rem; max-width: 780px; margin-bottom: 1rem; }}

  /* hero */
  .hero {{ padding: 2rem 0 1.4rem 0; }}
  .hero .big {{ font-family: 'Instrument Serif', serif !important; font-size: 4.2rem; line-height: .98; color: {INK};
                letter-spacing: -.01em; }}
  .hero .big i {{ color: {GOLD}; }}
  .hero .sub {{ font-family: 'JetBrains Mono', monospace !important; color: #6b675d; margin-top: .8rem; font-size: .9rem; }}

  /* cards */
  .card {{ background: #fffdf8; border: 1px solid #1b1b1b1a; border-radius: 16px; padding: 1.1rem 1.25rem;
           height: 100%; transition: transform .15s ease, box-shadow .15s ease; }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(27,27,27,.07); }}
  .card .num {{ font-family: 'JetBrains Mono', monospace !important; font-size: .74rem; color: #8a8576; }}
  .card .t {{ font-family: 'Instrument Serif', serif !important; font-weight: 400; font-size: 1.6rem; margin: .1rem 0 .3rem 0;
              color: {INK}; line-height: 1.1; padding: 0; }}
  .card .blurb {{ color: #5b574d; font-size: .86rem; line-height: 1.45; min-height: 7.4em; margin-bottom: .6rem; }}
  .card .changed {{ font-family: 'JetBrains Mono', monospace !important; font-size: .72rem; color: #7a5f00;
                    background: #fbf1cf; border-radius: 6px; padding: .15rem .45rem; display: inline-block;
                    margin-bottom: .5rem; }}
  .stat {{ display: flex; justify-content: space-between; align-items: baseline; padding: .32rem 0;
           border-top: 1px dashed #1b1b1b1f; font-size: .86rem; gap: .5rem; color: #3b3830; }}
  .stat b {{ font-family: 'JetBrains Mono', monospace !important; font-weight: 600; color: {INK}; white-space: nowrap; }}
  .stat b.best {{ color: {GOLD}; }}
  .d {{ font-family: 'JetBrains Mono', monospace !important; font-size: .68rem; font-weight: 600; margin-left: .3rem; }}
  .d.good {{ color: #1e7b3c; }} .d.bad {{ color: #b3261e; }}
  .step-card p {{ color: #5b574d; font-size: .9rem; line-height: 1.5; margin: .2rem 0 0 0; }}
  .arrow {{ font-family: 'JetBrains Mono', monospace !important; color: {GOLD}; }}
  .small {{ font-family: 'JetBrains Mono', monospace !important; font-size: .74rem; color: #8a8576; margin-bottom: .4rem; }}
  .stButton > button, .stDownloadButton > button {{ border-radius: 99px; font-weight: 500; }}
  @media (max-width: 800px) {{ .hero .big {{ font-size: 2.8rem; }} .h {{ font-size: 1.9rem; }} }}
</style>
""", unsafe_allow_html=True)


def head(kicker, title, lead=""):
    st.markdown(f'<div class="kicker">{kicker}</div><div class="h">{title}</div>'
                + (f'<div class="lead">{lead}</div>' if lead else ""), unsafe_allow_html=True)


# ============================================================================ Load data (before drawing tabs)
ENGINE = backend.engine_available()
COLUMNS = ENGINE and backend.columns_supported()
SHEETS = [("club", "Club sheet"), ("prof", "Professor sheet"), ("lecture", "Lecture catalog")]
NOT_IN_FILE = "— not in this file —"
SAMPLE = tuple(ROOT / f for f in ("club_info.csv", "prof_info.csv", "lecture_info.csv"))
SAMPLE_OK = all(p.exists() for p in SAMPLE)

uploads = {k: st.session_state.get(f"up_{k}") for k in ("club", "prof", "lecture")}
all_uploaded = all(uploads.values())
use_sample = SAMPLE_OK and not all_uploaded and st.session_state.get("use_sample", not any(uploads.values()))
files = SAMPLE if use_sample else (tuple(uploads.values()) if all_uploaded else None)
file_key = (tuple(str(f) if isinstance(f, Path) else (f.name, f.size, f.file_id) for f in files)
            if files else None)


def col_overrides():
    """Only the column choices staff made by hand; everything else is auto-detected."""
    return {s: m for s, m in st.session_state.get("colmap", {}).items() if m}


COL_KEY = json.dumps(col_overrides(), sort_keys=True) if COLUMNS else "{}"


@st.cache_data(show_spinner=False, max_entries=16)
def detect(_files, fkey, ckey):
    return backend.detect_columns(*_files, columns=json.loads(ckey) or None)


@st.cache_data(show_spinner=False, max_entries=64)
def compute(_files, fkey, wkey, ckey):
    return backend.run(*_files, weights=dict(wkey) if wkey else None, columns=json.loads(ckey) or None)


def run_with(weights):
    wkey = tuple(sorted(weights.items())) if (weights and ENGINE) else None
    return compute(files, file_key, wkey, COL_KEY)


def missing_required(det):
    out = []
    for sheet, label in SHEETS:
        mapping = det.get(sheet, {}).get("mapping", {})
        for f in backend.column_spec().get(sheet, []):
            if f.get("required") and not mapping.get(f["field"]):
                out.append(f"{label}: {f['label']}")
    return out


levels = current_levels() if ENGINE else STANDARD
weights = levels_to_weights(levels) if ENGINE else None
is_standard = (not ENGINE) or levels == STANDARD

detected, gaps, load_error, baseline, result = None, [], None, None, None
if files:
    try:
        if COLUMNS:
            detected = detect(files, file_key, COL_KEY)
            gaps = missing_required(detected)
        if not gaps:
            with st.spinner("Matching…"):
                baseline = run_with(levels_to_weights(STANDARD))
                result = baseline if is_standard else run_with(weights)
    except Exception as e:
        load_error = str(e)

ready = result is not None and any(len(p.matches) for p in result.plans.values())

# ============================================================================ Top bar
pills = []
if result is not None:
    sev = result.issues["Severity"].str.lower() if len(result.issues) else pd.Series(dtype=str)
    n_err, n_warn = int((sev == "error").sum()), int((sev == "warning").sum())
    pills += [f'<span class="pill">{result.n_clubs} clubs</span>',
              f'<span class="pill">{result.n_profs} professors</span>']
    pills.append(f'<span class="pill err">{n_err} to fix</span>' if n_err else '<span class="pill ok">data ok</span>')
    if n_warn:
        pills.append(f'<span class="pill warn">{n_warn} warnings</span>')
    if ENGINE:
        pills.append(f'<span class="pill">settings: {st.session_state.get("preset") or "custom"}</span>')
elif gaps or load_error:
    pills.append('<span class="pill err">needs attention · see Your data</span>')
else:
    pills.append('<span class="pill warn">waiting for sheets</span>')

st.markdown(f"""
<div class="topbar">
  <div class="brand"><span class="mark">Hesburgh <i>Lecture</i> Matching</span>
       <span class="tag">notre dame alumni association</span></div>
  <div class="status">{''.join(pills)}</div>
</div>""", unsafe_allow_html=True)

T_HOW, T_DATA, T_SET, T_PLANS, T_DL = st.tabs(
    ["01  How it works", "02  Your data", "03  Settings", "04  Plans", "05  Download"])

# ============================================================================ 01 How it works
with T_HOW:
    st.markdown("""
<div class="hero">
  <div class="big">Every club, the <i>right</i> speaker.</div>
  <div class="sub">Upload three sheets. Tune what matters. Compare plans. Download the one you like.</div>
</div>""", unsafe_allow_html=True)

    steps = [
        ("02", "Your data", "Drop in club_info, prof_info and lecture_info. The app checks them and tells you "
                            "what to fix before anything is matched."),
        ("03", "Settings", "Pick a preset or move the sliders: club size, engagement, clubs' choices, seniority, "
                           "repeat speakers. Plans update instantly."),
        ("04", "Plans", "Several plans side by side. Every match comes with the reason behind it, and every "
                        "unmatched club with why and who came closest."),
        ("05", "Download", "Pick the plans you want and get one Excel file, with the settings recorded inside."),
    ]
    for c, (n, t, body) in zip(st.columns(4, gap="medium"), steps):
        c.markdown(f'<div class="card step-card"><div class="num">{n} <span class="arrow">↗</span></div>'
                   f'<div class="t">{t}</div><p>{body}</p></div>', unsafe_allow_html=True)

    modes = list(result.plans.values()) if result is not None else []
    WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    head("The plans", f"{WORDS.get(len(modes), 'Several')} ways to <i>match</i>",
         "Every plan follows the same hard rules: one speaker per club, no professor over their event limit, "
         "and a match needs a shared month and a shared topic. They differ in what they reward.")
    if modes:
        for i, (c, p) in enumerate(zip(st.columns(len(modes), gap="medium"), modes), 1):
            c.markdown(f'<div class="card"><div class="num">0{i}</div><div class="t">{p.label}</div>'
                       f'<div class="blurb" style="min-height:0">{p.blurb}</div></div>', unsafe_allow_html=True)

    head("Good to know", "Questions staff <i>ask</i>")
    q1, q2 = st.columns(2, gap="large")
    with q1:
        with st.expander("What is the match score?"):
            st.write("Points for a requested lecture (10 each), a shared theme (5), a shared month (2) and a "
                     "shared format (1), scaled by the club's size and engagement and the speaker's seniority. "
                     "Your settings change how much each of those counts.")
        with st.expander("Why didn't a club get a speaker?"):
            st.write("The Plans tab lists every unmatched club with the reason (no availability, no shared "
                     "months, no topic overlap, or every suitable professor already booked) and the three "
                     "closest professors.")
        with st.expander("Which plan should we use?"):
            st.write("Start with Best fit. If it leans too hard on a few professors, look at Balanced. If "
                     "clubs' wishes matter most, look at Clubs' top choices. Gold numbers on the Plans tab show "
                     "which plan leads on each measure.")
    with q2:
        with st.expander("Someone renamed a column. Will it break?"):
            st.write("New or reordered columns are fine, and small renames are recognised. If a required "
                     "column can't be found, the app says which one and you can point it at the right column "
                     "under Settings > Columns.")
        with st.expander("Is our data stored anywhere?"):
            st.write("No. The sheets are read in memory for your session and are not saved by the app.")
        with st.expander("Can we reuse last year's settings?"):
            st.write("Yes. Settings > Save or load downloads a small file. Load it next time to restore the "
                     "same priorities and column choices.")

# ============================================================================ 02 Your data
with T_DATA:
    head("Step 02", "Your <i>data</i>", "Upload this year's three sheets as CSV files.")
    c1, c2, c3 = st.columns(3, gap="medium")
    c1.file_uploader("Club info", type="csv", key="up_club", help="club_info.csv")
    c2.file_uploader("Professor info", type="csv", key="up_prof", help="prof_info.csv")
    c3.file_uploader("Lecture catalog", type="csv", key="up_lecture", help="lecture_info.csv")
    if SAMPLE_OK and not all_uploaded:
        if "use_sample" not in st.session_state:
            st.session_state["use_sample"] = not any(uploads.values())
        st.toggle("Use the 2026 sheets already on file", key="use_sample")

    if not files:
        missing = [n for n, k in (("club info", "club"), ("professor info", "prof"),
                                  ("lecture catalog", "lecture")) if not uploads[k]]
        st.info(f"Still needed: {', '.join(missing)}.")
    elif load_error:
        st.error(f"The sheets couldn't be read: {load_error}. Check that the right file is in each box.")
    elif gaps:
        st.error("Some required columns couldn't be found, probably because a heading changed. Open "
                 "**03 Settings > Columns** and point each one at the right column:\n\n"
                 + "\n".join(f"- {g}" for g in gaps))
    elif result is not None:
        issues = result.issues
        sev = issues["Severity"].str.lower() if len(issues) else pd.Series(dtype=str)
        n_err, n_warn = int((sev == "error").sum()), int((sev == "warning").sum())
        st.markdown("<div class='kicker'>Data check</div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Clubs", result.n_clubs)
        m2.metric("Professors", result.n_profs)
        m3.metric("Problems to fix", n_err)
        m4.metric("Warnings", n_warn)
        if not ready:
            st.error("No matches could be made from these sheets. The problems below explain why.")
        if len(issues):
            icon = {"error": "🔴 Problem", "warning": "🟡 Warning", "info": "🔵 Note"}
            view = st.segmented_control("Show", ["All", "Problems", "Warnings", "Notes"], default="All",
                                        key="issue_view")
            want = {"Problems": {"error"}, "Warnings": {"warning"}, "Notes": {"info"}}.get(view or "All")
            show = issues[sev.isin(want)] if want else issues
            show = show.assign(Severity=show["Severity"].str.lower().map(lambda s: icon.get(s, s)))
            st.dataframe(show, hide_index=True, width="stretch", height=min(420, 38 + 35 * max(len(show), 1)),
                         column_config={"Details": st.column_config.TextColumn(width="large")})
            st.caption("Problems leave someone out of matching. Fix them in the sheet and upload it again.")
        else:
            st.success("No data problems found.")


# ============================================================================ 03 Settings
def on_column(sheet, field, wkey):
    v = st.session_state.get(wkey)
    v = list(v) if isinstance(v, list) else (None if v == NOT_IN_FILE else v)
    cm = st.session_state.setdefault("colmap", {})
    cm[sheet] = {**cm.get(sheet, {}), field: v}


def on_columns_reset():
    st.session_state["colmap"] = {}


def columns_panel(det):
    """One dropdown per field, showing what was detected and letting staff point it elsewhere."""
    spec = backend.column_spec()
    over = col_overrides()
    st.caption("The app finds each piece of information by its column heading. If a heading was renamed, "
               "pick the right column. ✓ found automatically · ✎ chosen by you · ⚠ required but missing")
    for col, (sheet, label) in zip(st.columns(len(SHEETS), gap="large"), SHEETS):
        info = det.get(sheet, {})
        headers = list(info.get("headers", []))
        mapping = info.get("mapping", {})
        with col:
            st.markdown(f"<div class='kicker'>{label}</div>", unsafe_allow_html=True)
            for f in spec.get(sheet, []):
                field, name, req = f["field"], f["label"], f.get("required")
                cur = mapping.get(field)
                mark = "✎" if field in over.get(sheet, {}) else ("✓" if cur else ("⚠" if req else "·"))
                tip = (f.get("meaning") or "") + (" (required)" if req else " (optional)")
                if f.get("multi"):
                    key = f"colm_{sheet}_{field}_{hash(file_key)}"
                    st.multiselect(f"{mark} {name}", headers, default=[c for c in (cur or []) if c in headers],
                                   key=key, help=tip, on_change=on_column, args=(sheet, field, key))
                else:
                    opts = [NOT_IN_FILE] + headers
                    key = f"cols_{sheet}_{field}_{hash(file_key)}"
                    st.selectbox(f"{mark} {name}", opts, index=opts.index(cur) if cur in headers else 0,
                                 key=key, help=tip, on_change=on_column, args=(sheet, field, key))
    if over:
        st.button("↺ Go back to automatic detection", on_click=on_columns_reset)


with T_SET:
    head("Step 03", "Your <i>settings</i>", "Changes apply to every plan straight away.")
    if not ENGINE:
        if backend.ENGINE_ERROR:
            st.warning("The upgraded matching engine failed to load, so results use the original code. "
                       f"Details for the developer: {backend.ENGINE_ERROR}")
        st.info("Settings need the upgraded matching engine.")
    else:
        sub = st.tabs(["Priorities", f"Columns{' ✎' if col_overrides() else ''}{' ⚠' if gaps else ''}",
                       "Save or load"])
        with sub[0]:
            top_l, top_r = st.columns([5, 1.3], vertical_alignment="bottom")
            with top_l:
                st.segmented_control("Start from a preset", list(PRESETS), key="preset", on_change=on_preset,
                                     help="Presets set the controls below. You can fine-tune from there.")
            with top_r:
                st.button("↺ Reset to standard", on_click=on_reset, width="stretch",
                          disabled=levels == STANDARD)
            g1, g2 = st.columns(2, gap="large")
            for col, group, kick, note in (
                    (g1, "all", "Who gets priority", "Applies to every plan."),
                    (g2, "balanced", "Fairness across faculty", "Shapes the Balanced plan.")):
                with col, st.container(border=True):
                    st.markdown(f"<div class='kicker' style='margin-top:0'>{kick}</div>"
                                f"<div class='small'>{note}</div>", unsafe_allow_html=True)
                    for k, label, help_, _, g in PRIORITIES:
                        if g == group:
                            st.select_slider(label, LEVELS, key=f"lvl_{k}", help=help_, on_change=on_slider)
            diffs = [f"{lab} ({levels[k]})" for k, lab, *_ in PRIORITIES if levels[k] != "Standard"]
            st.caption(f"**Current: {st.session_state.get('preset') or 'Custom'}.** " + (
                "Changed from standard: " + ", ".join(diffs) + "." if diffs
                else "Everything at its standard level."))
        with sub[1]:
            if detected:
                columns_panel(detected)
            else:
                st.info("Add the three sheets under 02 Your data to see their columns.")
        with sub[2]:
            st.write("Save your priorities and column choices to a small file, and load it next time to pick "
                     "up exactly where you left off. An old weights.json also works.")
            a, b = st.columns(2, gap="large")
            a.download_button("⤓ Save settings",
                              json.dumps({"preset": st.session_state.get("preset") or "Custom",
                                          "weights": weights, "columns": col_overrides()}, indent=2),
                              file_name="hesburgh_settings.json", mime="application/json", width="stretch")
            b.file_uploader("Load settings (.json)", type="json", key="settings_file",
                            on_change=on_settings_upload, label_visibility="collapsed")
            msg = st.session_state.pop("settings_msg", None)
            if msg:
                (st.success if msg[0] == "ok" else st.error)(msg[1])


# ============================================================================ 04 Plans
HIGHER = {"Clubs matched", "Professors used", "Total score", "Average score", "Regions covered",
          "Got their 1st choice", "Got a requested lecture", "Agrees with staff picks"}
LOWER = {"Repeat speakers", "Most events for one prof", "Month clashes"}
NO_DELTA = {"Total score", "Average score"}  # scores are on the priority scale, so not comparable
HIDE = {"Clubs total", "Professors total"}


def not_ready_note():
    if not files:
        st.info("Add the three sheets under **02 Your data** first.")
    else:
        st.warning("No plans yet. **02 Your data** explains what needs fixing.")


with T_PLANS:
    head("Step 04", "Compare the <i>plans</i>",
         "Gold marks the plan that leads on each measure." + (
             " Small green and red numbers show the change from standard settings." if not is_standard else ""))
    if not ready:
        not_ready_note()
    else:
        plans = list(result.plans.values())
        base_plans = baseline.plans

        def leader(metric):
            vals = [p.summary.get(metric) for p in plans]
            if metric in HIGHER:
                target = max(vals)
            elif metric in LOWER:
                target = min(vals)
            else:
                return set()
            if all(v == target for v in vals):
                return set()
            return {p.key for p in plans if p.summary.get(metric) == target}

        def pairing(plan):
            return dict(zip(plan.matches["Club"], plan.matches["Professor"])) if len(plan.matches) else {}

        def changed_clubs(plan):
            base = base_plans.get(plan.key)
            if base is None:
                return []
            a, b = pairing(base), pairing(plan)
            return [{"Club": c, "Standard settings": a.get(c, "— not matched"),
                     "Your settings": b.get(c, "— not matched")}
                    for c in sorted(set(a) | set(b)) if a.get(c) != b.get(c)]

        leaders = {k: leader(k) for k in plans[0].summary}
        for i, (col, p) in enumerate(zip(st.columns(len(plans), gap="medium"), plans), 1):
            bp = base_plans.get(p.key)
            rows = ""
            for k, v in p.summary.items():
                if k in HIDE:
                    continue
                shown = (f"{v} / {p.summary['Clubs total']}" if k == "Clubs matched" else
                         f"{v} / {p.summary['Professors total']}" if k == "Professors used" else v)
                cls = ' class="best"' if p.key in leaders.get(k, set()) else ""
                delta = ""
                if not is_standard and bp is not None and k not in NO_DELTA:
                    dv = v - bp.summary.get(k, v)
                    if dv:
                        good = (dv > 0) == (k in HIGHER)
                        delta = (f'<span class="d {"good" if good else "bad"}">'
                                 f'{"+" if dv > 0 else "−"}{abs(dv):g}</span>')
                rows += f'<div class="stat"><span>{k}</span><span><b{cls}>{shown}</b>{delta}</span></div>'
            badge = ""
            if not is_standard:
                n = len(changed_clubs(p))
                badge = (f'<div class="changed">{n} club{"s" if n != 1 else ""} changed</div>' if n
                         else '<div class="changed">same as standard</div>')
            col.markdown(f'<div class="card"><div class="num">0{i}</div><div class="t">{p.label}</div>'
                         f'<div class="blurb">{p.blurb}</div>{badge}{rows}</div>', unsafe_allow_html=True)

        head("Look closer", "Inside a <i>plan</i>")
        labels = [p.label for p in plans]
        if st.session_state.get("plan_view") not in labels:
            st.session_state["plan_view"] = labels[0]
        st.segmented_control("Plan", labels, key="plan_view", label_visibility="collapsed")
        p = next(pl for pl in plans if pl.label == (st.session_state.get("plan_view") or labels[0]))

        inner = ["Matches", f"Not matched ({len(p.unmatched)})", "Professor load"]
        if not is_standard:
            inner.append(f"Changes ({len(changed_clubs(p))})")
        it = st.tabs(inner)
        score_max = float(max((pl.matches["Score"].max() for pl in plans if len(pl.matches)), default=1) or 1)
        with it[0]:
            f1, f2 = st.columns([3, 2])
            q = f1.text_input("Search", key=f"q_{p.key}", placeholder="Search a club or professor",
                              label_visibility="collapsed")
            regions = sorted(r for r in p.matches.get("Region", pd.Series(dtype=str)).dropna().unique() if r)
            reg = f2.multiselect("Region", regions, key=f"r_{p.key}", placeholder="All regions",
                                 label_visibility="collapsed")
            m = p.matches
            if q:
                m = m[m["Club"].str.contains(q, case=False, regex=False)
                      | m["Professor"].str.contains(q, case=False, regex=False)]
            if reg:
                m = m[m["Region"].isin(reg)]
            st.caption(f"{len(m)} of {len(p.matches)} matches")
            st.dataframe(
                m, hide_index=True, width="stretch", height=430,
                column_order=[c for c in ["Club", "Professor", "Title", "Score", "Why", "Choice", "Month",
                                          "Repeat speaker", "Prof events", "Staff pick", "Region", "Size",
                                          "Engagement"] if c in m.columns],
                column_config={
                    "Score": st.column_config.ProgressColumn("Score", format="%.1f", min_value=0,
                                                             max_value=score_max),
                    "Repeat speaker": st.column_config.CheckboxColumn("Repeat?"),
                    "Why": st.column_config.TextColumn("Why this match", width="large"),
                    "Choice": st.column_config.TextColumn("Club's choice"),
                    "Month": st.column_config.TextColumn("Suggested month"),
                })
        with it[1]:
            if len(p.unmatched):
                st.dataframe(p.unmatched, hide_index=True, width="stretch", height=430,
                             column_order=["Club", "Reason", "Closest options", "Region", "Size"],
                             column_config={"Closest options": st.column_config.TextColumn(width="large")})
            else:
                st.success("Every club got a speaker in this plan.")
        with it[2]:
            load = p.matches["Professor"].value_counts().rename("Events")
            a, b = st.columns([3, 1])
            with a:
                st.bar_chart(load, color=NAVY, horizontal=True, height=430, sort="-Events")
            with b:
                st.metric("Professors used", len(load))
                st.metric("Most events for one", int(load.max()) if len(load) else 0)
                st.metric("With 2+ events", int((load >= 2).sum()))
        if not is_standard:
            with it[3]:
                ch = changed_clubs(p)
                if ch:
                    st.dataframe(pd.DataFrame(ch), hide_index=True, width="stretch", height=430)
                else:
                    st.write("This plan is the same as with standard settings.")


# ============================================================================ 05 Download
@st.cache_data(show_spinner=False, max_entries=64)
def excel_bytes(_result, fkey, wkey, ckey, keys, settings_items):
    return backend.to_excel(_result, list(keys), dict(settings_items))


with T_DL:
    head("Step 05", "Take it <i>with you</i>",
         "Pick the plans you want. You get one Excel file with a comparison sheet, the matches and unmatched "
         "clubs for each plan, the data check, and the settings used.")
    if not ready:
        not_ready_note()
    else:
        plans = list(result.plans.values())
        wkey = tuple(sorted(weights.items())) if weights else None
        settings_items = tuple({lab: levels[k] for k, lab, *_ in PRIORITIES}.items())
        labels = {p.label: p.key for p in plans}
        with st.container(border=True):
            chosen = st.pills("Plans to include", list(labels), selection_mode="multi", default=list(labels),
                              key="dl_pick")
            keys = tuple(labels[c] for c in (chosen or []))
            if keys:
                name = ("hesburgh_all_plans.xlsx" if len(keys) == len(plans) else
                        f"hesburgh_{keys[0]}.xlsx" if len(keys) == 1 else "hesburgh_selected_plans.xlsx")
                st.download_button(f"⤓ Download {len(keys)} plan{'s' if len(keys) != 1 else ''} (Excel)",
                                   excel_bytes(result, file_key, wkey, COL_KEY, keys, settings_items),
                                   file_name=name, type="primary", mime=XLSX)
            else:
                st.info("Pick at least one plan.")
        st.caption(f"Settings in this file: {st.session_state.get('preset') or 'Custom'}. "
                   "Not sure which plan? The 04 Plans tab shows each one in full.")
    if result is not None and result.source != "engine":
        st.caption("Preview mode: running on the original matching code.")
