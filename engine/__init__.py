"""Hesburgh Lecture matching engine: pairs Notre Dame faculty with alumni clubs.

    from engine import load_inputs, data_issues, run_plans, compare_plans

    data  = load_inputs("club_info.csv", "prof_info.csv", "lecture_info.csv")
    plans = run_plans(data)                 # {"best_fit": Plan, "balanced": Plan, ...}
    print(compare_plans(plans))

How it fits together (read in this order):
    text.py     forgiving helpers for months, names and quotes
    columns.py  finds each field by meaning, so renamed or added columns still work
    model.py    Club, Professor, Lecture, Request
    loader.py   CSVs -> model, plus a list of data issues
    scoring.py  how good one professor is for one club
    modes.py    what each plan optimises, one small function per mode
    solver.py   picks the pairs (exact Hungarian, or the old greedy)
    plans.py    turns picks into the matches / unmatched / summary tables

The contract other code may rely on is in API.md.
"""
from .columns import COLUMN_SPEC
from .loader import data_issues, detect_columns, load_inputs
from .model import MatchData
from .plans import DEFAULT_MODES, MODES, SUMMARY_LABELS, Plan, compare_plans, run_plans
from .scoring import WEIGHT_INFO, Weights

__all__ = ["load_inputs", "data_issues", "detect_columns", "COLUMN_SPEC", "run_plans", "compare_plans", "Weights", "Plan",
           "MatchData", "MODES", "DEFAULT_MODES", "SUMMARY_LABELS", "WEIGHT_INFO"]
