"""Command line:  python3 -m engine [CLUBS PROFS LECTURES] [--weights FILE] [--out DIR] [--modes LIST]

With no file arguments it looks for club_info.csv, prof_info.csv and
lecture_info.csv (and weights.json, if present) in the current folder.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from . import (DEFAULT_MODES, MODES, SUMMARY_LABELS, Weights, compare_plans, data_issues,
               load_inputs, run_plans)

DEFAULT_FILES = ("club_info.csv", "prof_info.csv", "lecture_info.csv")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m engine",
                                 description="Match Notre Dame faculty with alumni clubs for the Hesburgh Lectures.")
    ap.add_argument("files", nargs="*", metavar="CSV", help="club, professor and lecture CSVs, in that order")
    ap.add_argument("--weights", help="weights.json (default: ./weights.json if it exists)")
    ap.add_argument("--columns", help="JSON file saying where fields live, e.g. {\"club\": {\"size\": \"Club Size\"}}")
    ap.add_argument("--out", default="OUTPUTS", help="folder for the result CSVs (default: OUTPUTS)")
    ap.add_argument("--modes", default=",".join(DEFAULT_MODES),
                    help="comma-separated plans to build; choose from " + ", ".join(MODES))
    args = ap.parse_args(argv)
    if len(args.files) not in (0, 3):
        ap.error("give all three CSVs (clubs, professors, lectures) or none")
    args.files = args.files or list(DEFAULT_FILES)
    if args.weights is None and Path("weights.json").exists():
        args.weights = "weights.json"
    return args


def main(argv=None):
    args = parse_args(argv)
    columns = json.loads(Path(args.columns).read_text(encoding="utf-8")) if args.columns else None
    data = load_inputs(*args.files, columns=columns)
    weights = Weights.from_json(args.weights) if args.weights else None
    plans = run_plans(data, weights, [m.strip() for m in args.modes.split(",") if m.strip()])
    issues = data_issues(data)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(issues, columns=["severity", "kind", "subject", "message"]).to_csv(out / "data_issues.csv", index=False)
    for key, plan in plans.items():
        plan.matches.to_csv(out / f"{key}_matches.csv", index=False)
        plan.unmatched.to_csv(out / f"{key}_unmatched.csv", index=False)
    table = compare_plans(plans)
    table.to_csv(out / "plan_comparison.csv")

    print(f"\n{data.n_clubs} clubs, {data.n_profs} professors, {len(issues)} data notes"
          f"{' (weights from ' + args.weights + ')' if args.weights else ''}\n")
    readable = table.T.rename(index=SUMMARY_LABELS).loc[[SUMMARY_LABELS[k] for k in SUMMARY_LABELS if k in table.columns]]
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:g}".format):
        print(readable.to_string())
    print()
    for plan in plans.values():
        print(f"  {plan.label}: {plan.description}")
    print(f"\nWrote {2 * len(plans) + 2} files to {out.resolve()}")


if __name__ == "__main__":
    main()
