"""Run from the project folder: python3 -m unittest engine.tests.test_engine"""
import io
import itertools
import random

import pandas as pd
import unittest
from pathlib import Path

import csv

from engine import load_inputs, data_issues, detect_columns, run_plans, compare_plans, Weights, COLUMN_SPEC
from engine.text import parse_months, split_request, clean
from engine.solver import best_assignment

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "club_info.csv", ROOT / "prof_info.csv", ROOT / "lecture_info.csv"]


class TestParsing(unittest.TestCase):
    def test_month_ranges(self):
        self.assertEqual(parse_months("January-March, November-December"),
                         ["January", "February", "March", "November", "December"])
        self.assertEqual(parse_months("April,May,"), ["April", "May"])
        self.assertEqual(len(parse_months("August,All of the above")), 12)
        self.assertEqual(parse_months(""), [])

    def test_hyphen_in_title_survives(self):
        theme, title = split_request(
            "Leadership | Leading People in an Ever-Changing World- January-May, September-December")
        self.assertEqual((theme, title), ("Leadership", "Leading People in an Ever-Changing World"))

    def test_associate_titles_rank_below_full_titles(self):
        from engine.loader import senior_title
        self.assertEqual(senior_title("Vice President and Associate Provost"), "vice president")
        self.assertEqual(senior_title("Professor; Associate Dean for the Social Sciences"), "associate dean")
        self.assertEqual(senior_title("Dean of the Mendoza College of Business"), "dean")

    def test_quotes_compare_equal(self):
        self.assertEqual(clean("Can’t"), clean("Can't"))


class TestRealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_inputs(*FILES)
        cls.plans = run_plans(cls.data, modes=["legacy_greedy", "recommended", "best_fit", "most_clubs", "balanced", "top_choices"])

    def test_first_professor_kept_and_everyone_has_lectures(self):
        names = [p.name for p in self.data.profs]
        self.assertIn("Francisco Aragon", names)
        self.assertEqual(len(names), 41)
        self.assertTrue(all(p.lectures for p in self.data.profs))

    def test_name_typos_reported(self):
        fixed = {i["subject"] for i in data_issues(self.data) if i["kind"] == "name_mismatch"}
        self.assertTrue({"Margaret Pfeil", "Michael Pippenger", "Walter Sheirer", "Francisco Aragon"} <= fixed)

    def test_curly_apostrophe_lecture_credit(self):
        akron = self.plans["best_fit"].matches.set_index("club").loc["Akron"]
        self.assertEqual(akron["professor"], "David Chiang")
        self.assertIn("Large Language Models", akron["shared_lectures"])

    def test_hard_rules_every_mode(self):
        caps = {p.name: p.max_events for p in self.data.profs}
        for key, plan in self.plans.items():
            m = plan.matches
            self.assertFalse(m["club"].duplicated().any(), key)
            for prof, n in m["professor"].value_counts().items():
                self.assertLessEqual(n, caps[prof], key)
            self.assertTrue((m["shared_months"] != "").all(), key)
            self.assertTrue(((m["shared_themes"] != "") | (m["shared_lectures"] != "")).all(), key)
            self.assertEqual(len(m) + len(plan.unmatched), self.data.n_clubs, key)

    def test_best_fit_is_at_least_greedy(self):
        self.assertGreaterEqual(self.plans["best_fit"].summary["total_score"],
                                self.plans["legacy_greedy"].summary["total_score"])

    def test_mode_tradeoffs(self):
        s = {k: p.summary for k, p in self.plans.items()}
        self.assertGreaterEqual(s["balanced"]["profs_used"], s["best_fit"]["profs_used"])
        self.assertLessEqual(s["balanced"]["repeat_speakers"], s["best_fit"]["repeat_speakers"])
        self.assertGreaterEqual(s["top_choices"]["first_choice_lectures"], s["best_fit"]["first_choice_lectures"])
        self.assertGreaterEqual(s["most_clubs"]["clubs_matched"], s["best_fit"]["clubs_matched"])
        # Recommended: as many clubs as Most clubs, as many 1st choices as Top choices, no repeats.
        self.assertEqual(s["recommended"]["clubs_matched"], s["most_clubs"]["clubs_matched"])
        self.assertGreaterEqual(s["recommended"]["first_choice_lectures"], s["top_choices"]["first_choice_lectures"])
        self.assertEqual(s["recommended"]["repeat_speakers"], 0)

    def test_unmatched_have_reasons(self):
        for plan in self.plans.values():
            self.assertTrue((plan.unmatched["reason"] != "").all())

    def test_compare_table(self):
        t = compare_plans(self.plans)
        self.assertEqual(len(t), 6)
        self.assertIn("total_score", t.columns)


class TestScarcity(unittest.TestCase):
    def test_most_clubs_serves_more_when_capacity_is_tight(self):
        data = load_inputs(*FILES)
        for p in data.profs:
            p.max_events = 1
        plans = run_plans(data)
        self.assertGreaterEqual(plans["most_clubs"].summary["clubs_matched"],
                                plans["best_fit"].summary["clubs_matched"])
        for plan in plans.values():
            self.assertLessEqual(plan.summary["max_events_per_prof"], 1)


class TestInputs(unittest.TestCase):
    def test_file_like_inputs(self):
        data = load_inputs(*[io.BytesIO(f.read_bytes()) for f in FILES])
        self.assertEqual(data.n_clubs, 52)

    def test_blank_size_and_score_do_not_crash(self):
        text = FILES[0].read_text(encoding="utf-8").splitlines(keepends=True)
        import csv
        rows = list(csv.reader(text))
        hdr = rows[0]
        rows[1][hdr.index("Size")] = ""
        rows[1][hdr.index("HLS Score")] = ""
        buf = io.StringIO()
        csv.writer(buf).writerows(rows)
        data = load_inputs(io.StringIO(buf.getvalue()), FILES[1], FILES[2])
        kinds = {i["kind"] for i in data_issues(data)}
        self.assertTrue({"blank_size", "blank_score"} <= kinds)
        run_plans(data)

    def test_missing_required_column_is_reported_not_raised(self):
        data = load_inputs(io.StringIO("a,b\n1,2\n"), FILES[1], FILES[2])
        errors = [i for i in data_issues(data) if i["kind"] == "missing_column"]
        self.assertTrue(errors)
        self.assertIn("club_info.csv", errors[0]["subject"])
        self.assertEqual(data.n_clubs, 0)
        run_plans(data)                     # still produces (empty) plans

    def test_weights_are_multipliers(self):
        w = Weights.coerce({"size_weight": 0.7, "eng_weight": 1.2, "title_weight": 1.1})
        self.assertEqual((w.size, w.engagement, w.title), (0.7, 1.2, 1.1))
        data = load_inputs(*FILES)
        flat = run_plans(data, {"size": 0, "engagement": 0, "title": 0}, ["best_fit"])["best_fit"].matches
        normal = run_plans(data, None, ["best_fit"])["best_fit"].matches
        self.assertGreater(flat["score"].nunique(), 10)   # scores do not collapse to a few values
        self.assertFalse(flat["score"].equals(normal["score"]))


class TestSolver(unittest.TestCase):
    def test_matches_brute_force(self):
        rng = random.Random(7)
        for _ in range(40):
            nc, npf = rng.randint(1, 5), rng.randint(1, 3)
            caps = [rng.randint(1, 2) for _ in range(npf)]
            W = {(c, p): (rng.uniform(1, 10) if rng.random() < 0.7 else None) for c in range(nc) for p in range(npf)}
            sol = best_assignment(nc, caps, lambda c, p: W[c, p])
            got = sum(W[c, p] for c, p in enumerate(sol) if p is not None)
            best = 0.0
            for combo in itertools.product([None] + list(range(npf)), repeat=nc):
                if any(p is not None and W[c, p] is None for c, p in enumerate(combo)):
                    continue
                if any(combo.count(p) > caps[p] for p in range(npf)):
                    continue
                best = max(best, sum(W[c, p] for c, p in enumerate(combo) if p is not None))
            self.assertAlmostEqual(got, best, places=6)


def _edited_csv(path: Path, rename=None, shuffle=False, extra=None) -> io.StringIO:
    """Copy a CSV with headers renamed, columns shuffled and/or extra columns added."""
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines(keepends=True)))
    header = [(rename or {}).get(h.strip(), h) for h in rows[0]]
    body = rows[1:]
    for name in extra or []:
        header.append(name)
        body = [r + ["?"] for r in body]
    order = list(range(len(header)))
    if shuffle:
        random.Random(3).shuffle(order)
    out = io.StringIO()
    csv.writer(out).writerows([[r[i] if i < len(r) else "" for i in order] for r in [header, *body]])
    out.seek(0)
    return out


class TestChangingColumns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = run_plans(load_inputs(*FILES))

    def assertSamePlans(self, data):
        for key, plan in run_plans(data).items():
            pd.testing.assert_frame_equal(plan.matches, self.baseline[key].matches)

    def test_shuffled_renamed_and_extra_columns(self):
        clubs = _edited_csv(FILES[0], shuffle=True, extra=["Notes 2027", "Invited 2025"],
                            rename={"HLS Score": "hls_score", "Club Check": "Club Name", "Availability": "Availabilty"})
        profs = _edited_csv(FILES[1], shuffle=True, rename={"Recipient Full Name": "Full Name",
                                                             "# of Events": "Number of Events"})
        lectures = _edited_csv(FILES[2], shuffle=True, rename={"Topic": "Lecture Title"})
        data = load_inputs(clubs, profs, lectures)
        self.assertEqual((data.n_clubs, data.n_profs), (52, 41))
        self.assertEqual(data.columns["club"]["invited"], "Invited 2026")      # newest year wins
        self.assertFalse([i for i in data_issues(data) if i["severity"] == "error"])
        self.assertSamePlans(data)

    def test_extra_theme_column_and_new_year_are_picked_up(self):
        data = load_inputs(_edited_csv(FILES[0], extra=["Theme 6", "2026 Speaker"]), FILES[1], FILES[2])
        self.assertEqual(data.columns["club"]["themes"][-1], "Theme 6")
        self.assertEqual(data.columns["club"]["past_speakers"][0], "2026 Speaker")

    def test_override_for_unrecognisable_header(self):
        clubs = lambda: _edited_csv(FILES[0], rename={"Size": "Club Tier"})
        self.assertIsNone(load_inputs(clubs(), FILES[1], FILES[2]).columns["club"]["size"])
        data = load_inputs(clubs(), FILES[1], FILES[2], columns={"club": {"size": "Club Tier"}})
        self.assertEqual(data.columns["club"]["size"], "Club Tier")
        self.assertSamePlans(data)

    def test_override_naming_a_missing_column_is_reported(self):
        data = load_inputs(*FILES, columns={"club": {"size": "Nope"}})
        self.assertTrue(any("Nope" in i["message"] for i in data_issues(data)))

    def test_detect_columns_and_spec(self):
        found = detect_columns(*FILES)
        self.assertEqual(found["prof"]["mapping"]["max_events"], "# of Events")
        self.assertIn("Theme 1", found["club"]["headers"])
        spec_fields = {f["field"] for f in COLUMN_SPEC["club"]}
        self.assertEqual(spec_fields, set(found["club"]["mapping"]))


if __name__ == "__main__":
    unittest.main()
