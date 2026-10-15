"""
Hesburgh Lecture Matching: staff app.

Run locally:   streamlit run ui/app.py
"""
import json
from pathlib import Path

import altair as alt
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
    # key, label, one-line summary, values per level, group
    ("size", "Bigger clubs first", "Larger clubs get the strongest speakers before smaller clubs do.",
     [0, 0.5, 1, 1.5, 2], "who"),
    ("engagement", "Most active clubs first", "Clubs with a higher engagement (HLS) score get priority.",
     [0, 0.5, 1, 1.5, 2], "who"),
    ("choice_rank", "Respect clubs' rankings", "How strongly to favour the talk a club ranked 1st over its later picks.",
     [0, 0.5, 1, 1.5, 2], "what"),
    ("lecture_match", "Exact talk requested", "How much more an exact requested talk counts than just the same topic area.",
     [0, 0.5, 1, 1.5, 2], "what"),
    ("month_overlap", "Easy to schedule", "Favour pairs who are both free in many of the same months.",
     [0, 0.5, 1, 1.5, 2], "what"),
    ("format_match", "Preferred talk format", "Favour professors who offer the format the club asked for (e.g. Q&A).",
     [0, 0.5, 1, 1.5, 2], "what"),
    ("title", "Senior speakers", "Give deans, provosts and directors a boost for the most engaged clubs.",
     [0, 0.5, 1, 1.5, 2], "who"),
    ("staff_pick", "Agree with our team's picks", "Favour the speaker your team already pencilled in for a club.",
     [0, 0.5, 1, 1.5, 2], "what"),
    ("repeat_penalty", "Avoid repeat speakers", "Avoid sending a club someone who spoke to them in the last four years.",
     [0, 0.5, 1, 2, 3], "fair"),
    ("spread", "Share talks across faculty", "Avoid giving one professor several talks while others have none.",
     [0, 0.5, 1, 2, 3], "fair"),
    ("travel_bonus", "Honour travel wishes", "Favour clubs in places professors said they'd like to visit.",
     [0, 0.5, 1, 2, 3], "fair"),
]
# What staff see when they click "What does this do?"
EXPLAIN = {
    "size": "Clubs are sized AA (largest) down to F. Turning this up means a large club is more likely to get "
            "the speaker it asked for when two clubs want the same professor. Turning it off treats every club "
            "the same regardless of size.",
    "engagement": "Each club has an engagement (HLS) score from its activity. Turning this up favours clubs with "
                  "higher scores when there's competition for a speaker. Off ignores the score.",
    "choice_rank": "Clubs list up to five talks in order. At Max, getting a club its 1st choice matters much more "
                   "than its 3rd. At Off, any talk on the club's list counts the same.",
    "lecture_match": "A club can ask for a specific talk or just a topic area. Higher values reward giving clubs the "
                     "exact talk they named. Lower values are happy with any talk in the right topic.",
    "month_overlap": "When a professor and a club share many free months, the event is easier to schedule. Higher "
                     "values prefer those pairs. This never overrides the rule that they must share at least one month.",
    "format_match": "Clubs choose formats such as a lecture with Q&A or a fireside chat. Higher values prefer "
                    "professors who offer that format. It only makes a difference when the spreadsheets include "
                    "talk formats, so this year it may change little or nothing.",
    "title": "Deans, provosts and directors can get a small boost so they go to the most engaged clubs. Off "
             "treats every title the same.",
    "staff_pick": "If your team already pencilled in a speaker for a club (the '2026 Assignment' column), higher "
                  "values make the plans more likely to keep that choice.",
    "repeat_penalty": "Uses the 2022–2025 speaker columns. Higher values steer clubs away from someone they've "
                      "already heard. Off allows repeats freely. Mainly affects the Balanced and Recommended plans.",
    "spread": "Professors can offer several talks. Higher values spread talks across more faculty instead of "
              "giving a few people most of them. Mainly affects the Balanced plan.",
    "travel_bonus": "Professors can name places they'd like to visit. Higher values favour sending them there. "
                    "Mainly affects the Balanced and Recommended plans.",
}
GROUPS = [("who", "Which clubs come first"), ("what", "What makes a good match"),
          ("fair", "Fairness to clubs and faculty")]


def _engine_weight_keys():
    try:
        import engine
        return set(engine.Weights.__dataclass_fields__)
    except Exception:
        return {"size", "engagement", "title", "choice_rank", "repeat_penalty", "spread", "travel_bonus"}


# Only offer the dials the matching engine actually understands.
PRIORITIES = [p for p in PRIORITIES if p[0] in _engine_weight_keys()]
PKEYS = [p[0] for p in PRIORITIES]
STANDARD = {k: "Standard" for k in PKEYS}
PRESETS = {
    "Standard": {},
    "Big clubs first": {"size": "Max", "engagement": "Low"},
    "Active clubs first": {"engagement": "Max", "size": "Low"},
    "Clubs' wishes first": {"choice_rank": "Max", "lecture_match": "High", "title": "Low"},
    "Fresh faces": {"repeat_penalty": "Max", "spread": "High"},
    "Share the faculty": {"spread": "Max", "repeat_penalty": "High", "travel_bonus": "High"},
    "Keep our picks": {"staff_pick": "Max"},
}
PRESETS = {n: v for n, v in PRESETS.items() if n == "Standard" or any(k in PKEYS for k in v)}
LEGACY_KEYS = {"size_weight": "size", "eng_weight": "engagement", "title_weight": "title"}


def preset_levels(name):
    return {**STANDARD, **{k: v for k, v in PRESETS[name].items() if k in STANDARD}}


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
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Libre+Baskerville:wght@400;700&display=swap');
  .stApp, .stApp :is(p, label, input, textarea, button, li, td, th, div) {{
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, 'Segoe UI', sans-serif; }}
  [data-testid="stAppViewContainer"] {{ background: {PAPER}; }}
  [data-testid="stHeader"], [data-testid="stSidebarCollapsedControl"], [data-testid="stToolbar"] {{ display: none; }}
  .block-container {{ padding-top: 0; padding-bottom: 3rem; max-width: 1280px; }}

  /* header band */
  .band {{ background: {NAVY}; margin: -1rem -100vw 0 -100vw; padding: 1.15rem 100vw 1.05rem 100vw;
           border-bottom: 4px solid {GOLD}; }}
  .band-inner {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }}
  .brand .over {{ color: {GOLD}; font-size: .72rem; font-weight: 600; letter-spacing: .14em;
                  text-transform: uppercase; }}
  .brand .mark {{ font-family: 'Libre Baskerville', Georgia, serif !important; color: #fff; font-size: 1.65rem;
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
  .h {{ font-family: 'Libre Baskerville', Georgia, serif !important; font-size: 1.6rem; font-weight: 700;
        line-height: 1.15; color: {NAVY}; margin: 0 0 .35rem 0; }}
  .lead {{ color: #4a5468; font-size: .98rem; max-width: 820px; margin-bottom: 1rem; line-height: 1.55; }}

  /* intro */
  .intro {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 2rem; align-items: center; padding: 1.6rem 0 .6rem 0; }}
  .intro .big {{ font-family: 'Libre Baskerville', Georgia, serif !important; font-size: 2.5rem; font-weight: 700;
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
  .card .t {{ font-family: 'Libre Baskerville', Georgia, serif !important; font-weight: 700; font-size: 1.22rem;
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
SHEETS = [("club", "Club requests sheet"), ("prof", "Professor sheet"), ("lecture", "Lecture list")]
NOT_IN_FILE = "(not in this sheet)"
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


def plain(f):
    """A field's name in everyday words, e.g. 'Months the club can host'."""
    text = (f.get("meaning") or f["label"]).split(",")[0].split(" (")[0].split(" '")[0]
    return text[0].upper() + text[1:]


def missing_required(det):
    out = []
    for sheet, label in SHEETS:
        mapping = det.get(sheet, {}).get("mapping", {})
        for f in backend.column_spec().get(sheet, []):
            if f.get("required") and not mapping.get(f["field"]):
                out.append((sheet, f))
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

# ============================================================================ Extra styles for guidance
st.markdown(f"""
<style>
  .next {{ display: flex; gap: .9rem; align-items: flex-start; background: #fff; border: 1px solid {LINE};
           border-left: 5px solid {GOLD}; border-radius: 10px; padding: .85rem 1.1rem; margin: 1.1rem 0 .4rem 0; }}
  .next .lbl {{ color: {GOLD_DARK}; font-size: .72rem; font-weight: 700; letter-spacing: .1em;
                text-transform: uppercase; white-space: nowrap; padding-top: .15rem; }}
  .next .msg {{ color: #24324a; font-size: .97rem; line-height: 1.5; }}
  .next.bad {{ border-left-color: #b3261e; }} .next.bad .lbl {{ color: #b3261e; }}
  .next.good {{ border-left-color: #1e7b3c; }} .next.good .lbl {{ color: #1e7b3c; }}
  .need {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px; padding: 1rem 1.25rem; }}
  .need ol {{ margin: .3rem 0 0 1.1rem; padding: 0; color: #3a4456; }}
  .need li {{ margin: .35rem 0; line-height: 1.5; }}
  .need b {{ color: {NAVY}; }}
  .tip {{ color: #5a6475; font-size: .88rem; margin-top: .6rem; }}
  .stat.win {{ background: #fff6da; margin: 0 -.5rem; padding-left: .5rem; padding-right: .5rem;
                border-radius: 6px; border-top-color: transparent; }}
  .strong {{ font-size: .8rem; color: #24324a; background: #f2f5f9; border-radius: 6px; padding: .35rem .55rem;
             margin-bottom: .55rem; line-height: 1.45; }}
  .strong span {{ color: {GOLD_DARK}; font-weight: 700; text-transform: uppercase; font-size: .68rem;
                  letter-spacing: .08em; margin-right: .25rem; }}
  .strong.none {{ color: #6b7486; }}
  .pick ul {{ margin: .4rem 0 0 1.1rem; padding: 0; }} .pick li {{ margin: .25rem 0; }}
  .pick .cost {{ color: #6b6250; }}
  .pick {{ background: #fffaf0; border: 1px solid #f0dfae; border-radius: 10px; padding: .75rem 1rem;
           color: #4a3b00; margin: .3rem 0 1rem 0; font-size: .95rem; }}
</style>
""", unsafe_allow_html=True)

# ============================================================================ Header
st.markdown("""
<div class="band"><div class="band-inner">
  <div class="brand"><div class="over">Notre Dame Alumni Association</div>
       <div class="mark">Hesburgh Lecture Series · Speaker Matching</div></div>
</div></div>""", unsafe_allow_html=True)

TAB_NAMES = ["Start here", "1 · Upload sheets", "2 · Adjust priorities", "3 · Compare plans",
             "4 · Dashboard", "5 · Download"]
T_HOW, T_DATA, T_SET, T_PLANS, T_DASH, T_DL = st.tabs(TAB_NAMES)


def next_step(where):
    """A plain 'what to do now' box at the top of every tab."""
    up, pr, cp, db, dl = (f"<b>{n}</b>" for n in TAB_NAMES[1:])
    if not files:
        kind, msg = "", f"Open the {up} tab at the top of the page and add your three spreadsheets."
    elif load_error or gaps:
        kind, msg = "bad", f"Some information couldn't be found in your spreadsheets. Open {up} to fix it."
    elif not ready:
        kind, msg = "bad", f"No matches could be made from these spreadsheets. {up} explains why."
    else:
        kind, msg = "good", {
            "how": f"Your spreadsheets are loaded. Go to {cp} to see the results.",
            "data": f"Your spreadsheets look ready. Next, open {cp} to see the results. "
                    f"(You can change priorities in {pr} first, but you don't have to.)",
            "set": f"When you're happy with these, open {cp} to see how the plans changed.",
            "plans": f"For charts of each plan, open {db}. When you've chosen a plan, open {dl} to save it.",
            "dash": f"When you've chosen a plan, open {dl} to save it as an Excel file.",
            "dl": "Save the Excel file and share it with your team. You can come back and change things any time.",
        }[where]
    st.markdown(f'<div class="next {kind}"><span class="lbl">What to do now</span>'
                f'<span class="msg">{msg}</span></div>', unsafe_allow_html=True)


# ============================================================================ Start here
with T_HOW:
    next_step("how")
    st.markdown("""
<div class="intro">
  <div><div class="big">Match every alumni club with a Notre Dame speaker.</div>
       <div class="sub">This tool reads this year's club requests and professor availability, suggests
       who should speak where, and explains each suggestion. You stay in charge: compare the options,
       then download the one you want as an Excel file.</div></div>
  <div class="need"><b>Before you start, have these three spreadsheets ready:</b>
    <ol>
      <li><b>Club requests</b>: the clubs' sign-up sheet (usually called <i>club_info</i>)</li>
      <li><b>Professors</b>: the faculty availability sheet (<i>prof_info</i>)</li>
      <li><b>Lecture list</b>: the list of talks on offer (<i>lecture_info</i>)</li>
    </ol>
    <div class="tip">In Google Sheets, use File, then Download, then Microsoft Excel (.xlsx) or
    Comma-separated values (.csv). Either works.</div>
  </div>
</div>""", unsafe_allow_html=True)

    head("How it works", "Five simple steps")
    steps = [
        ("1", "Upload sheets", "Add the three spreadsheets. The tool checks them and points out anything "
                               "missing, such as a club that didn't give its available months."),
        ("2", "Adjust priorities", "Optional. Choose what matters most this year, for example bigger clubs "
                                   "or avoiding repeat speakers. The standard settings work well."),
        ("3", "Compare plans", "See a few complete options side by side, with every club's speaker and the "
                               "reason it was chosen. Recommended is a good place to start."),
        ("4", "Dashboard", "Charts that show at a glance how the plans differ: how many clubs get a "
                           "speaker, first choices, repeat speakers and talks by month."),
        ("5", "Download", "Save the plans you like as an Excel file to share with your team."),
    ]
    for c, (n, t, body) in zip(st.columns(5, gap="small"), steps):
        c.markdown(f'<div class="card step-card"><div class="num">{n}</div>'
                   f'<div class="t">{t}</div><p>{body}</p></div>', unsafe_allow_html=True)

    modes = list(result.plans.values()) if result is not None else []
    if modes:
        head("The options you'll see", "Each plan answers a slightly different question",
             "Every plan follows the same rules: each club gets at most one speaker, no professor is asked "
             "to give more talks than they offered, and a club is only matched with a professor who is free "
             "in one of the club's months and offers a topic the club asked for.")
        for i, (c, p) in enumerate(zip(st.columns(len(modes), gap="medium"), modes), 1):
            rec = p.key == "recommended"
            c.markdown(f'<div class="card{" rec" if rec else ""}"><div class="num">{i}</div>'
                       f'{"<span class=badge>Start here</span>" if rec else ""}<div class="t">{p.label}</div>'
                       f'<div class="blurb" style="min-height:0">{p.blurb}</div></div>', unsafe_allow_html=True)

    head("Common questions", "Good to know")
    q1, q2 = st.columns(2, gap="large")
    with q1:
        with st.expander("Which plan should we use?"):
            st.write("Start with Recommended. It gives a speaker to as many clubs as possible, then tries to "
                     "give each club the talk it ranked highest, while avoiding repeat speakers and spreading "
                     "talks across faculty. The other plans are there if you want to compare.")
        with st.expander("Why didn't a club get a speaker?"):
            st.write("On the Compare plans tab, open 'Clubs without a speaker'. Each club has a plain reason "
                     "(for example, it didn't list any months) and the professors you could ask instead.")
        with st.expander("What does 'match strength' mean?"):
            st.write("A rough measure of how good a pairing is. It goes up when the professor offers the exact "
                     "talk the club asked for, shares more available months, and when the club is larger or more "
                     "engaged. Higher is better; it's only used to compare options.")
    with q2:
        with st.expander("Someone changed a column heading in the spreadsheet. Is that a problem?"):
            st.write("Usually not. The tool recognises most small changes and ignores extra columns. If it "
                     "can't find something important, the Upload sheets tab will ask you to point to the right "
                     "column with a simple drop-down.")
        with st.expander("What does each priority do?"):
            st.write("In Adjust priorities, every setting has a 'What does this do?' link underneath it that "
                     "explains it in plain words, with an example. 'Standard' is a sensible default for all.")
        with st.expander("Is our data saved anywhere?"):
            st.write("No. Your spreadsheets are only used while this page is open and are not stored.")
        with st.expander("Can we reuse this year's settings next year?"):
            st.write("Yes. In Adjust priorities, choose 'Save or reuse settings' to download a small settings "
                     "file. Next year, load it there to start from the same choices.")


# ============================================================================ Column fixer (used in two places)
def on_column(sheet, field, wkey):
    v = st.session_state.get(wkey)
    v = list(v) if isinstance(v, list) else (None if v == NOT_IN_FILE else v)
    cm = st.session_state.setdefault("colmap", {})
    cm[sheet] = {**cm.get(sheet, {}), field: v}


def on_columns_reset():
    st.session_state["colmap"] = {}


def column_picker(det, sheet, f, where):
    """A drop-down for one piece of information. It always shows the column currently in use, so the
    same field shown on two tabs never disagrees."""
    info = det.get(sheet, {})
    headers = list(info.get("headers", []))
    cur = info.get("mapping", {}).get(f["field"])
    tip = f"Usually the column headed “{f['label']}”."
    if f.get("multi"):
        key = f"colm_{where}_{sheet}_{f['field']}_{hash(file_key)}"
        st.session_state[key] = [c for c in (cur or []) if c in headers]
        st.multiselect(plain(f), headers, key=key, help=tip, placeholder="Choose the columns",
                       on_change=on_column, args=(sheet, f["field"], key))
    else:
        opts = [NOT_IN_FILE] + headers
        key = f"cols_{where}_{sheet}_{f['field']}_{hash(file_key)}"
        st.session_state[key] = cur if cur in headers else NOT_IN_FILE
        st.selectbox(plain(f), opts, key=key, help=tip, on_change=on_column, args=(sheet, f["field"], key))


def columns_panel(det):
    st.write("The tool finds information by each column's heading. If a heading was changed, choose the "
             "column that now holds that information. Everything else is found automatically.")
    spec = backend.column_spec()
    for col, (sheet, label) in zip(st.columns(len(SHEETS), gap="large"), SHEETS):
        with col:
            st.markdown(f"<div class='kicker'>{label}</div>", unsafe_allow_html=True)
            for f in spec.get(sheet, []):
                column_picker(det, sheet, f, "settings")
    if col_overrides():
        st.button("Undo my column choices", on_click=on_columns_reset)


# ============================================================================ 1 Upload sheets
with T_DATA:
    next_step("data")
    head("Step 1", "Upload this year's spreadsheets", "Excel (.xlsx) or CSV files both work.")
    c1, c2, c3 = st.columns(3, gap="medium")
    c1.file_uploader("Club requests (club_info)", type=["xlsx", "csv"], key="up_club",
                     help="The clubs' sign-up sheet, with their months and the talks they'd like.")
    c2.file_uploader("Professors (prof_info)", type=["xlsx", "csv"], key="up_prof",
                     help="The faculty sheet, with each professor's months and how many talks they'll give.")
    c3.file_uploader("Lecture list (lecture_info)", type=["xlsx", "csv"], key="up_lecture",
                     help="The list of talks, with the professor who gives each one.")
    if SAMPLE_OK and not all_uploaded:
        if "use_sample" not in st.session_state:
            st.session_state["use_sample"] = not any(uploads.values())
        st.toggle("Use the 2026 spreadsheets already saved here", key="use_sample",
                  help="Turn this off to use the files you upload above.")

    if not files:
        missing = [n for n, k in (("club requests", "club"), ("professors", "prof"),
                                  ("lecture list", "lecture")) if not uploads[k]]
        st.info(f"Still needed: {', '.join(missing)}.")
    elif load_error:
        st.error("We couldn't read one of the files. Check that each box has the right spreadsheet, saved as "
                 "Excel or CSV.")
        with st.expander("Technical details (for whoever maintains this tool)"):
            st.code(load_error)
    elif gaps:
        st.error("We couldn't find some information we need, probably because a column heading was changed. "
                 "For each item below, choose the column that holds it.")
        with st.container(border=True):
            for sheet, f in gaps:
                st.markdown(f"<div class='kicker' style='margin-top:.2rem'>{dict(SHEETS)[sheet]}</div>",
                            unsafe_allow_html=True)
                column_picker(detected, sheet, f, "upload")
    elif result is not None:
        issues = result.issues
        sev = issues["Severity"].str.lower() if len(issues) else pd.Series(dtype=str)
        n_err, n_warn = int((sev == "error").sum()), int((sev == "warning").sum())
        head("Check", "What we found in your spreadsheets")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Clubs", result.n_clubs)
        m2.metric("Professors", result.n_profs)
        m3.metric("Must fix", n_err, help="Something that leaves a club or professor out entirely.")
        m4.metric("Worth a look", n_warn, help="Matching still works, but you may want to check these.")
        if not ready:
            st.error("No matches could be made from these spreadsheets. The list below explains why.")
        if len(issues):
            labels = {"error": "Must fix", "warning": "Worth a look", "info": "For your information"}
            view = st.segmented_control("Show", ["Everything", "Must fix", "Worth a look", "For your information"],
                                        default="Everything", key="issue_view")
            want = {v: k for k, v in labels.items()}.get(view or "Everything")
            show = issues[sev == want] if want else issues
            show = pd.DataFrame({
                "Type": show["Severity"].str.lower().map(lambda s: labels.get(s, s)),
                "About": show["Who"], "What we noticed": show["Details"], "Category": show["Issue"]})
            st.dataframe(show, hide_index=True, width="stretch", height=min(420, 38 + 35 * max(len(show), 1)),
                         column_config={"What we noticed": st.column_config.TextColumn(width="large")})
            st.caption("To fix something, correct it in the spreadsheet, save it, and upload it again here.")
        else:
            st.success("Everything looks good.")


# ============================================================================ 2 Adjust priorities
with T_SET:
    next_step("set")
    head("Step 2 (optional)", "Adjust priorities",
         "The standard settings work well for most years. Change these only if you'd like the plans to "
         "favour something different. The results update as soon as you make a change.")
    if not ENGINE:
        st.info("These options aren't available right now. The plans use the standard settings.")
        if backend.ENGINE_ERROR:
            with st.expander("Technical details (for whoever maintains this tool)"):
                st.code(backend.ENGINE_ERROR)
    else:
        sub = st.tabs(["Priorities", "Save or reuse settings", "If a column heading changed"])
        with sub[0]:
            top_l, top_r = st.columns([5, 1.3], vertical_alignment="bottom")
            with top_l:
                st.segmented_control("Quick choices", list(PRESETS), key="preset", on_change=on_preset,
                                     help="Each quick choice sets the sliders below. You can adjust from there.")
            with top_r:
                st.button("Back to standard", on_click=on_reset, width="stretch", disabled=levels == STANDARD)
            st.caption("Each slider runs from Off to Max. Standard is the recommended setting. Click "
                       "“What does this do?” under any slider for a plain explanation.")
            gcols = st.columns(len(GROUPS), gap="medium")
            for col, (gkey, gtitle) in zip(gcols, GROUPS):
                items = [p for p in PRIORITIES if p[4] == gkey]
                if not items:
                    continue
                with col, st.container(border=True):
                    st.markdown(f"<div class='kicker' style='margin-top:0'>{gtitle}</div>", unsafe_allow_html=True)
                    for k, label, summary, _, _ in items:
                        st.select_slider(label, LEVELS, key=f"lvl_{k}", on_change=on_slider)
                        st.markdown(f"<div class='small' style='margin-top:-.6rem'>{summary}</div>",
                                    unsafe_allow_html=True)
                        with st.popover("What does this do?", type="tertiary"):
                            st.markdown(f"**{label}**")
                            st.write(EXPLAIN.get(k, summary))
                            st.caption("Off ignores this completely. Standard is the usual setting. "
                                       "Max makes it count about twice as much.")
            diffs = [f"{lab} ({levels[k]})" for k, lab, *_ in PRIORITIES if levels[k] != "Standard"]
            st.caption("You're using the standard settings." if not diffs else
                       "Changed from standard: " + ", ".join(diffs) + ".")
        with sub[1]:
            st.write("Save these choices to a small file on your computer. Next time, load it here to start from "
                     "the same settings.")
            a, b = st.columns(2, gap="large")
            a.download_button("Save my settings",
                              json.dumps({"preset": st.session_state.get("preset") or "Custom",
                                          "weights": weights, "columns": col_overrides()}, indent=2),
                              file_name="hesburgh_settings.json", mime="application/json", width="stretch")
            b.file_uploader("Load saved settings", type="json", key="settings_file",
                            on_change=on_settings_upload)
            msg = st.session_state.pop("settings_msg", None)
            if msg:
                (st.success if msg[0] == "ok" else st.error)(msg[1])
        with sub[2]:
            if detected:
                columns_panel(detected)
            else:
                st.info(f"Upload your spreadsheets in {TAB_NAMES[1]} first.")


# ============================================================================ 3 Compare plans
SHOW = [  # (summary key, label staff see)
    ("Clubs matched", "Clubs with a speaker"),
    ("Got their 1st choice", "Clubs getting their 1st choice"),
    ("Got a requested lecture", "Clubs getting a talk they asked for"),
    ("Repeat speakers", "Repeat speakers"),
    ("Professors used", "Professors giving talks"),
    ("Most events for one prof", "Most talks for one professor"),
    ("Agrees with staff picks", "Same as your team's picks"),
]
HIGHER = {"Clubs matched", "Professors used", "Got their 1st choice", "Got a requested lecture",
          "Agrees with staff picks"}
LOWER = {"Repeat speakers", "Most events for one prof"}


SHORT = {"Clubs matched": "clubs served", "Got their 1st choice": "1st choices",
         "Got a requested lecture": "requested talks", "Repeat speakers": "fewest repeats",
         "Professors used": "sharing talks across faculty", "Most events for one prof": "lightest busiest-professor load",
         "Agrees with staff picks": "matching your team's picks"}


def _diff_phrase(k, d):
    n = abs(d)
    return {
        "Clubs matched": f"{n} more club{'s' if n != 1 else ''} get{'s' if n == 1 else ''} a speaker",
        "Got their 1st choice": f"{n} more club{'s' if n != 1 else ''} get{'s' if n == 1 else ''} their 1st-choice talk",
        "Got a requested lecture": f"{n} more club{'s' if n != 1 else ''} get{'s' if n == 1 else ''} a talk they asked for",
        "Repeat speakers": f"{n} fewer repeat speaker{'s' if n != 1 else ''}",
        "Professors used": f"{n} more professor{'s' if n != 1 else ''} share{'s' if n == 1 else ''} the talks",
        "Most events for one prof": f"the busiest professor gives {n} fewer talk{'s' if n != 1 else ''}",
        "Agrees with staff picks": f"{n} more match{'es' if n != 1 else ''} with your team's picks",
    }[k]


def proof_box(plans):
    """Spell out, in numbers, what the first (recommended) plan gains over each alternative."""
    top = plans[0]
    lines = []
    for other in plans[1:]:
        gains, costs = [], []
        for k, _ in SHOW:
            a, b = top.summary.get(k), other.summary.get(k)
            if a is None or b is None or a == b:
                continue
            better = (a > b) if k in HIGHER else (a < b)
            (gains if better else costs).append(_diff_phrase(k, a - b))
        if gains:
            line = f"<li>Compared with <b>{other.label}</b>: " + "; ".join(gains)
            if costs:
                line += f". <span class='cost'>Trade-off: with {other.label}, {'; '.join(costs)}.</span>"
            lines.append(line + "</li>")
    if not lines:
        return ""
    return (f'<div class="pick"><b>Why {top.label}?</b> Not sure which to choose? Start with <b>{top.label}</b>. '
            f'Here is what it gains, in numbers:<ul>{"".join(lines)}</ul></div>')


def not_ready_note():
    if not files:
        st.info(f"Nothing to show yet. Upload your spreadsheets in {TAB_NAMES[1]} first.")
    else:
        st.warning(f"Nothing to show yet. {TAB_NAMES[1]} explains what needs fixing.")


with T_PLANS:
    next_step("plans")
    head("Step 3", "Compare the plans",
         "Each column is a complete plan. A gold star shows which plan does best on each line."
         + (" Green and red numbers show how your priorities changed things." if not is_standard else ""))
    if not ready:
        not_ready_note()
    else:
        plans = list(result.plans.values())
        base_plans = baseline.plans
        st.markdown(proof_box(plans), unsafe_allow_html=True)

        def leader(metric):
            vals = [p.summary.get(metric) for p in plans]
            if None in vals:
                return set()
            target = max(vals) if metric in HIGHER else min(vals)
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
            return [{"Club": c, "With standard settings": a.get(c, "No speaker"),
                     "With your settings": b.get(c, "No speaker")}
                    for c in sorted(set(a) | set(b)) if a.get(c) != b.get(c)]

        for i, (col, p) in enumerate(zip(st.columns(len(plans), gap="medium"), plans), 1):
            bp = base_plans.get(p.key)
            rows = ""
            for k, lab in SHOW:
                if k not in p.summary:
                    continue
                v = p.summary[k]
                shown = (f"{v} of {p.summary['Clubs total']}" if k == "Clubs matched" else
                         f"{v} of {p.summary['Professors total']}" if k == "Professors used" else v)
                win = p.key in leader(k)
                cls = ' class="best"' if win else ""
                delta = ""
                if not is_standard and bp is not None:
                    dv = v - bp.summary.get(k, v)
                    if dv:
                        good = (dv > 0) == (k in HIGHER)
                        delta = (f'<span class="d {"good" if good else "bad"}">'
                                 f'{"+" if dv > 0 else "−"}{abs(dv):g}</span>')
                rows += (f'<div class="stat{" win" if win else ""}"><span>{lab}</span>'
                         f'<span><b{cls}>{shown}</b>{delta}</span></div>')
            wins = [short for k, lab, short in [(k, lab, SHORT.get(k, lab)) for k, lab in SHOW]
                    if k in p.summary and p.key in leader(k)]
            strengths = (f'<div class="strong"><span>Best for</span> {", ".join(wins)}</div>' if wins
                         else '<div class="strong none">Doesn\'t lead on any measure</div>')
            badge = ""
            if not is_standard:
                n = len(changed_clubs(p))
                badge = (f'<div class="changed">{n} club{"s" if n != 1 else ""} changed</div>' if n
                         else '<div class="changed">No change</div>')
            rec = p.key == "recommended"
            col.markdown(f'<div class="card{" rec" if rec else ""}"><div class="num">{i}</div>'
                         f'{"<span class=badge>Recommended</span>" if rec else ""}<div class="t">{p.label}</div>'
                         f'<div class="blurb">{p.blurb}</div>{strengths}{badge}{rows}</div>', unsafe_allow_html=True)

        head("Details", "See who goes where")
        labels = [p.label for p in plans]
        if st.session_state.get("plan_view") not in labels:
            st.session_state["plan_view"] = labels[0]
        st.segmented_control("Choose a plan to look at", labels, key="plan_view")
        p = next(pl for pl in plans if pl.label == (st.session_state.get("plan_view") or labels[0]))

        inner = ["Who goes where", f"Clubs without a speaker ({len(p.unmatched)})", "Talks per professor"]
        if not is_standard:
            inner.append(f"What your priorities changed ({len(changed_clubs(p))})")
        it = st.tabs(inner)
        score_max = float(max((pl.matches["Score"].max() for pl in plans if len(pl.matches)), default=1) or 1)
        with it[0]:
            f1, f2 = st.columns([3, 2])
            q = f1.text_input("Find a club or professor", key=f"q_{p.key}", placeholder="Type a name, e.g. Chicago")
            regions = sorted(r for r in p.matches.get("Region", pd.Series(dtype=str)).dropna().unique() if r)
            reg = f2.multiselect("Region", regions, key=f"r_{p.key}", placeholder="All regions")
            m = p.matches
            if q:
                m = m[m["Club"].str.contains(q, case=False, regex=False)
                      | m["Professor"].str.contains(q, case=False, regex=False)]
            if reg:
                m = m[m["Region"].isin(reg)]
            st.caption(f"Showing {len(m)} of {len(p.matches)} clubs with a speaker.")
            st.dataframe(
                m, hide_index=True, width="stretch", height=430,
                column_order=[c for c in ["Club", "Professor", "Why", "Month", "Choice", "Repeat speaker",
                                          "Score", "Title", "Prof events", "Staff pick", "Region", "Size"]
                              if c in m.columns],
                column_config={
                    "Why": st.column_config.TextColumn("Why this match", width="large"),
                    "Month": st.column_config.TextColumn("Suggested month"),
                    "Choice": st.column_config.TextColumn("Club's ranking of this talk"),
                    "Repeat speaker": st.column_config.CheckboxColumn("Spoke to this club before?"),
                    "Score": st.column_config.ProgressColumn("Match strength", format="%.0f", min_value=0,
                                                             max_value=score_max),
                    "Title": st.column_config.TextColumn("Professor's title"),
                    "Prof events": st.column_config.TextColumn("Professor's talks"),
                    "Staff pick": st.column_config.TextColumn("Your team's pick"),
                    "Size": st.column_config.TextColumn("Club size"),
                })
        with it[1]:
            if len(p.unmatched):
                st.caption("These clubs didn't get a speaker in this plan. The last column suggests professors "
                           "you could ask directly.")
                st.dataframe(p.unmatched, hide_index=True, width="stretch", height=430,
                             column_order=["Club", "Reason", "Closest options", "Region", "Size"],
                             column_config={"Closest options": st.column_config.TextColumn(
                                 "Professors you could ask", width="large"),
                                 "Size": st.column_config.TextColumn("Club size")})
            else:
                st.success("Every club gets a speaker in this plan.")
        with it[2]:
            load = p.matches["Professor"].value_counts().rename("Talks")
            a, b = st.columns([3, 1])
            with a:
                st.bar_chart(load, color=NAVY, horizontal=True, height=430, sort="-Talks")
            with b:
                st.metric("Professors giving talks", len(load))
                st.metric("Most talks for one professor", int(load.max()) if len(load) else 0)
                st.metric("Professors with 2 or more", int((load >= 2).sum()))
        if not is_standard:
            with it[3]:
                ch = changed_clubs(p)
                if ch:
                    st.dataframe(pd.DataFrame(ch), hide_index=True, width="stretch", height=430)
                else:
                    st.write("Your priorities didn't change this plan.")


# ============================================================================ 4 Dashboard

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
SOFT = "#9AA8BD"   # the other plans, so the recommended one stands out in gold


def plan_bars(plans, key, title, note):
    df = pd.DataFrame({"Plan": [p.label for p in plans], "Value": [p.summary.get(key, 0) for p in plans],
                       "Highlight": [p.key == "recommended" for p in plans]})
    base = alt.Chart(df).encode(
        y=alt.Y("Plan:N", sort=None, title=None, axis=alt.Axis(labelLimit=200, labelFontSize=13)),
        x=alt.X("Value:Q", title=None, axis=alt.Axis(grid=False, labels=False, ticks=False, domain=False)))
    bars = base.mark_bar(cornerRadiusEnd=4, height=22).encode(
        color=alt.condition("datum.Highlight", alt.value(GOLD), alt.value(SOFT)),
        tooltip=[alt.Tooltip("Plan:N"), alt.Tooltip("Value:Q", title=title)])
    text = base.mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=NAVY).encode(text="Value:Q")
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(note)
        st.altair_chart((bars + text).properties(height=34 * len(plans) + 10), width="stretch")


def count_bars(series, title, note, order=None, top=None):
    counts = series[series.astype(str).str.strip() != ""].value_counts()
    if order:
        counts = counts.reindex([o for o in order if o in counts.index])
    else:
        counts = counts.sort_values(ascending=False)
    if top:
        counts = counts.head(top)
    df = counts.rename_axis("Label").reset_index(name="Talks")
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(note)
        if df.empty:
            st.write("No data for this yet.")
            return
        base = alt.Chart(df).encode(
            y=alt.Y("Label:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelFontSize=12)),
            x=alt.X("Talks:Q", title=None, axis=alt.Axis(grid=False, labels=False, ticks=False, domain=False)))
        chart = (base.mark_bar(color=NAVY, cornerRadiusEnd=4, height=16)
                 + base.mark_text(align="left", dx=5, fontSize=12, color=NAVY).encode(text="Talks:Q"))
        st.altair_chart(chart.properties(height=max(120, 24 * len(df))), width="stretch")


with T_DASH:
    next_step("dash")
    head("Dashboard", "The plans at a glance",
         "The same results as Compare plans, as charts. Gold is the Recommended plan.")
    if not ready:
        not_ready_note()
    else:
        plans = list(result.plans.values())
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            plan_bars(plans, "Clubs matched", "Clubs that get a speaker", "More is better.")
            plan_bars(plans, "Repeat speakers", "Clubs getting a speaker they've had before", "Fewer is better.")
        with c2:
            plan_bars(plans, "Got their 1st choice", "Clubs getting the talk they ranked first", "More is better.")
            plan_bars(plans, "Professors used", "Professors giving at least one talk",
                      "More means the work is shared more widely.")

        head("One plan in detail", "Where, when and who")
        labels = [p.label for p in plans]
        if st.session_state.get("dash_plan") not in labels:
            st.session_state["dash_plan"] = labels[0]
        st.segmented_control("Choose a plan", labels, key="dash_plan")
        p = next(pl for pl in plans if pl.label == (st.session_state.get("dash_plan") or labels[0]))
        m = p.matches
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Clubs with a speaker", f"{p.summary.get('Clubs matched', len(m))} of {p.summary.get('Clubs total', '')}")
        k2.metric("Got their 1st choice", p.summary.get("Got their 1st choice", "—"))
        k3.metric("Repeat speakers", p.summary.get("Repeat speakers", "—"))
        k4.metric("Professors giving talks", p.summary.get("Professors used", m["Professor"].nunique()))
        d1, d2 = st.columns(2, gap="medium")
        with d1:
            if "Month" in m:
                count_bars(m["Month"].fillna(""), "Talks by month", "The suggested month for each talk.", order=MONTHS)
            if "Choice" in m:
                ch = m["Choice"].fillna("").replace("", "Same topic, different talk")
                count_bars(ch, "How each club's talk ranked on its list",
                           "1st means the club gets the talk it wanted most.",
                           order=["1st", "2nd", "3rd", "4th", "5th", "Same topic, different talk"])
        with d2:
            if "Region" in m:
                count_bars(m["Region"].fillna(""), "Talks by region", "Where the talks will happen.")
            count_bars(m["Professor"], "Busiest professors", "The ten professors giving the most talks.", top=10)


# ============================================================================ 5 Download
@st.cache_data(show_spinner=False, max_entries=64)
def excel_bytes(_result, fkey, wkey, ckey, keys, settings_items):
    return backend.to_excel(_result, list(keys), dict(settings_items))


with T_DL:
    next_step("dl")
    head("Step 5", "Download your plan",
         "Choose the plan or plans you want. You'll get one Excel file with who goes where, the clubs "
         "without a speaker, and the settings that were used.")
    if not ready:
        not_ready_note()
    else:
        plans = list(result.plans.values())
        wkey = tuple(sorted(weights.items())) if weights else None
        settings_items = tuple({lab: levels[k] for k, lab, *_ in PRIORITIES}.items())
        labels = {p.label: p.key for p in plans}
        default = [plans[0].label]
        with st.container(border=True):
            chosen = st.pills("Which plans should the file include?", list(labels), selection_mode="multi",
                              default=default, key="dl_pick")
            keys = tuple(labels[c] for c in (chosen or []))
            if keys:
                name = ("hesburgh_all_plans.xlsx" if len(keys) == len(plans) else
                        f"hesburgh_{keys[0]}.xlsx" if len(keys) == 1 else "hesburgh_selected_plans.xlsx")
                st.download_button("Download Excel file",
                                   excel_bytes(result, file_key, wkey, COL_KEY, keys, settings_items),
                                   file_name=name, type="primary", mime=XLSX)
            else:
                st.info("Choose at least one plan above.")
    if result is not None and result.source != "engine":
        st.caption("Running in basic mode with the original matching method.")
