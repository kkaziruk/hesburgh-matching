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
GOLD = "#C99700"        # Notre Dame gold
GOLD_DARK = "#8C6A00"   # gold dark enough for text on white
NAVY = "#0C2340"        # Notre Dame navy
PAPER = "#F6F7F9"
LINE = "#DDE1E8"
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
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');
  .stApp, .stApp :is(p, label, input, textarea, button, li, td, th, div) {{
      font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; }}
  [data-testid="stAppViewContainer"] {{ background: {PAPER}; }}
  [data-testid="stHeader"], [data-testid="stSidebarCollapsedControl"], [data-testid="stToolbar"] {{ display: none; }}
  .block-container {{ padding-top: 0; padding-bottom: 3rem; max-width: 1280px; }}

  /* header band */
  .band {{ background: {NAVY}; margin: -1rem -100vw 0 -100vw; padding: 1.15rem 100vw 1.05rem 100vw;
           border-bottom: 4px solid {GOLD}; }}
  .band-inner {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }}
  .brand .over {{ color: {GOLD}; font-size: .72rem; font-weight: 600; letter-spacing: .14em;
                  text-transform: uppercase; }}
  .brand .mark {{ font-family: 'Source Serif 4', Georgia, serif !important; color: #fff; font-size: 1.65rem;
                  font-weight: 700; line-height: 1.15; }}
  .status {{ display: flex; flex-wrap: wrap; gap: .4rem; justify-content: flex-end; }}
  .pill {{ font-size: .76rem; font-weight: 500; border-radius: 99px; padding: .22rem .7rem; white-space: nowrap;
           background: rgba(255,255,255,.10); color: #e6ebf2; border: 1px solid rgba(255,255,255,.18); }}
  .pill.err {{ background: #fbe3e1; color: #8c1d18; border-color: #fbe3e1; }}
  .pill.warn {{ background: #fdf3d6; color: #6b5200; border-color: #fdf3d6; }}
  .pill.ok {{ background: #e3f1e7; color: #1e5b33; border-color: #e3f1e7; }}

  /* main tabs */
  div[data-testid="stTabs"] div[role="tablist"] {{ gap: 1.8rem; }}
  div[data-testid="stTabs"] button[role="tab"] p {{ font-size: .95rem; font-weight: 500; color: #5a6475; }}
  div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p {{ color: {NAVY}; font-weight: 600; }}
  div[data-baseweb="tab-highlight"] {{ background-color: {GOLD}; height: 3px; }}

  /* section headers */
  .kicker {{ color: {GOLD_DARK}; font-size: .74rem; font-weight: 700; letter-spacing: .12em;
             text-transform: uppercase; margin: 1.3rem 0 .2rem 0; }}
  .h {{ font-family: 'Source Serif 4', Georgia, serif !important; font-size: 1.85rem; font-weight: 700;
        line-height: 1.15; color: {NAVY}; margin: 0 0 .35rem 0; }}
  .lead {{ color: #4a5468; font-size: .98rem; max-width: 820px; margin-bottom: 1rem; line-height: 1.55; }}

  /* intro */
  .intro {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 2rem; align-items: center; padding: 1.6rem 0 .6rem 0; }}
  .intro .big {{ font-family: 'Source Serif 4', Georgia, serif !important; font-size: 2.5rem; font-weight: 700;
                 line-height: 1.12; color: {NAVY}; }}
  .intro .sub {{ color: #4a5468; margin-top: .7rem; font-size: 1.02rem; line-height: 1.6; }}
  .facts {{ background: #fff; border: 1px solid {LINE}; border-left: 4px solid {GOLD}; border-radius: 10px;
            padding: 1rem 1.2rem; }}
  .facts div {{ display: flex; justify-content: space-between; padding: .3rem 0; font-size: .92rem; color: #3a4456; }}
  .facts b {{ color: {NAVY}; }}
  @media (max-width: 900px) {{ .intro {{ grid-template-columns: 1fr; }} .intro .big {{ font-size: 2rem; }} }}

  /* cards */
  .card {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px; padding: 1.05rem 1.2rem; height: 100%;
           box-shadow: 0 1px 2px rgba(12,35,64,.04); }}
  .card.rec {{ border: 2px solid {GOLD}; box-shadow: 0 4px 16px rgba(201,151,0,.12); }}
  .card .num {{ display: inline-flex; align-items: center; justify-content: center; width: 1.6rem; height: 1.6rem;
                border-radius: 50%; background: {NAVY}; color: #fff; font-size: .78rem; font-weight: 600; }}
  .card .badge {{ display: inline-block; background: {GOLD}; color: #fff; font-size: .68rem; font-weight: 700;
                  letter-spacing: .08em; text-transform: uppercase; border-radius: 4px; padding: .12rem .45rem;
                  margin-left: .4rem; vertical-align: middle; }}
  .card .t {{ font-family: 'Source Serif 4', Georgia, serif !important; font-weight: 700; font-size: 1.22rem;
              margin: .45rem 0 .3rem 0; color: {NAVY}; line-height: 1.2; }}
  .card .blurb {{ color: #5a6475; font-size: .86rem; line-height: 1.5; min-height: 7.6em; margin-bottom: .6rem; }}
  .card .changed {{ font-size: .74rem; font-weight: 600; color: #6b5200; background: #fdf3d6; border-radius: 4px;
                    padding: .15rem .45rem; display: inline-block; margin-bottom: .5rem; }}
  .stat {{ display: flex; justify-content: space-between; align-items: baseline; padding: .34rem 0;
           border-top: 1px solid #eef0f4; font-size: .86rem; gap: .5rem; color: #3a4456; }}
  .stat b {{ font-weight: 600; color: {NAVY}; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .stat b.best {{ color: {GOLD_DARK}; }}
  .stat b.best::before {{ content: "★ "; font-size: .72rem; }}
  .d {{ font-size: .7rem; font-weight: 600; margin-left: .3rem; }}
  .d.good {{ color: #1e7b3c; }} .d.bad {{ color: #b3261e; }}
  .step-card p {{ color: #5a6475; font-size: .9rem; line-height: 1.55; margin: .2rem 0 0 0; }}
  .small {{ font-size: .8rem; color: #6b7486; margin-bottom: .4rem; }}
  .stButton > button, .stDownloadButton > button {{ border-radius: 6px; font-weight: 600; }}
  div[data-testid="stMetricValue"] {{ color: {NAVY}; }}
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
    pills.append(f'<span class="pill err">{n_err} to fix</span>' if n_err else '<span class="pill ok">Data OK</span>')
    if n_warn:
        pills.append(f'<span class="pill warn">{n_warn} warnings</span>')
    if ENGINE:
        pills.append(f'<span class="pill">Settings: {st.session_state.get("preset") or "Custom"}</span>')
elif gaps or load_error:
    pills.append('<span class="pill err">Needs attention: see Your data</span>')
else:
    pills.append('<span class="pill warn">Waiting for sheets</span>')

st.markdown(f"""
<div class="band"><div class="band-inner">
  <div class="brand"><div class="over">Notre Dame Alumni Association</div>
       <div class="mark">Hesburgh Lecture Series · Speaker Matching</div></div>
  <div class="status">{''.join(pills)}</div>
</div></div>""", unsafe_allow_html=True)

T_HOW, T_DATA, T_SET, T_PLANS, T_DL = st.tabs(
    ["How it works", "1 · Your data", "2 · Settings", "3 · Plans", "4 · Download"])

# ============================================================================ 01 How it works
with T_HOW:
    facts = ""
    if result is not None:
        rec = next(iter(result.plans.values()), None)
        facts = (f'<div><span>Clubs in this year\'s sheets</span><b>{result.n_clubs}</b></div>'
                 f'<div><span>Participating professors</span><b>{result.n_profs}</b></div>'
                 + (f'<div><span>Clubs matched ({rec.label})</span><b>{rec.summary.get("Clubs matched", "—")}</b></div>'
                    if rec else ""))
        facts = f'<div class="facts">{facts}</div>'
    st.markdown(f"""
<div class="intro">
  <div><div class="big">Pair every alumni club with the right Notre Dame speaker.</div>
       <div class="sub">Upload this year's club, professor and lecture sheets. The app checks the data, builds
       several complete matching plans, explains every match, and exports the plan you choose to Excel.</div></div>
  {facts}
</div>""", unsafe_allow_html=True)

    steps = [
        ("1", "Your data", "Drop in club_info, prof_info and lecture_info. The app checks them and tells you "
                            "what to fix before anything is matched."),
        ("2", "Settings", "Pick a preset or move the sliders: club size, engagement, clubs' choices, seniority, "
                           "repeat speakers. Plans update instantly."),
        ("3", "Plans", "Several plans side by side. Every match comes with the reason behind it, and every "
                        "unmatched club with why and who came closest."),
        ("4", "Download", "Pick the plans you want and get one Excel file, with the settings recorded inside."),
    ]
    for c, (n, t, body) in zip(st.columns(4, gap="medium"), steps):
        c.markdown(f'<div class="card step-card"><div class="num">{n}</div>'
                   f'<div class="t">{t}</div><p>{body}</p></div>', unsafe_allow_html=True)

    modes = list(result.plans.values()) if result is not None else []
    WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    head("The plans", f"{WORDS.get(len(modes), 'Several')} ways to match",
         "Every plan follows the same hard rules: one speaker per club, no professor over their event limit, "
         "and a match needs a shared month and a shared topic. They differ in what they reward.")
    if modes:
        for i, (c, p) in enumerate(zip(st.columns(len(modes), gap="medium"), modes), 1):
            rec = i == 1 and p.key == "recommended"
            c.markdown(f'<div class="card{" rec" if rec else ""}"><div class="num">{i}</div>'
                       f'{"<span class=badge>Recommended</span>" if rec else ""}<div class="t">{p.label}</div>'
                       f'<div class="blurb" style="min-height:0">{p.blurb}</div></div>', unsafe_allow_html=True)

    head("Good to know", "Common questions")
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
            st.write("Start with Recommended: it serves as many clubs as possible, then gives each the lecture "
                     "it wanted most while avoiding repeat speakers and spreading events across faculty. Compare "
                     "it with the others on the Plans tab, where a gold star marks the plan that leads on each "
                     "measure.")
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

# ============================================================================ Your data
with T_DATA:
    head("Step 1", "Your data", "Upload this year's three sheets as CSV files.")
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
                 "**Settings > Columns** and point each one at the right column:\n\n"
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
    head("Step 2", "Your settings", "Changes apply to every plan straight away.")
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
                st.info("Add the three sheets under Your data to see their columns.")
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
        st.info("Add the three sheets under **Your data** first.")
    else:
        st.warning("No plans yet. **Your data** explains what needs fixing.")


with T_PLANS:
    head("Step 3", "Compare the plans",
         "A gold star marks the plan that leads on each measure." + (
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
            rec = p.key == "recommended"
            col.markdown(f'<div class="card{" rec" if rec else ""}"><div class="num">{i}</div>'
                         f'{"<span class=badge>Recommended</span>" if rec else ""}<div class="t">{p.label}</div>'
                         f'<div class="blurb">{p.blurb}</div>{badge}{rows}</div>', unsafe_allow_html=True)

        head("Look closer", "Inside a plan")
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
    head("Step 4", "Download your plans",
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
                   "Not sure which plan? The Plans tab shows each one in full.")
    if result is not None and result.source != "engine":
        st.caption("Preview mode: running on the original matching code.")
