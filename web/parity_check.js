// Checks that web/engine.js gives exactly the same plans as the Python engine.
//
//   node web/parity_check.js [folder with club_info.csv, prof_info.csv, lecture_info.csv]
//
// The folder defaults to the repository root. Needs python3 with pandas.
// Run it after any change to engine/ or web/engine.js.
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const E = require("./engine.js");

const ROOT = process.env.ENGINE_ROOT || path.resolve(__dirname, "..");
const DATA = path.resolve(process.argv[2] || ROOT);
const WEIGHTS = [
  {},
  { spread: 0, repeat_penalty: 2, choice_rank: 0 },
  { size: 0, engagement: 2.5, title: 3, staff_pick: 1, travel_bonus: 3 },
  { lecture_match: 0.3, theme_match: 2, month_overlap: 0, format_match: 3 },
];

const PY = `
import json, sys
sys.path.insert(0, sys.argv[1])
from engine import load_inputs, data_issues, run_plans
from engine.modes import REGISTRY
d, cases = sys.argv[2], json.loads(sys.argv[3])
data = load_inputs(f"{d}/club_info.csv", f"{d}/prof_info.csv", f"{d}/lecture_info.csv")
out = {"issues": data_issues(data), "columns": data.columns, "cases": []}
for w in cases:
    c = {}
    for k, p in run_plans(data, w, list(REGISTRY)).items():
        c[k] = {"summary": p.summary,
                "matches": [[r.club_id, r.professor, float(r.score), r.suggested_month, r.why] for r in p.matches.itertuples()],
                "unmatched": [[r.club_id, r.reason, r.suggestion_1, r.suggestion_1_why, r.suggestion_2, r.suggestion_3] for r in p.unmatched.itertuples()]}
    out["cases"].append(c)
print(json.dumps(out, default=str))
`;

const py = JSON.parse(execFileSync("python3", ["-c", PY, ROOT, DATA, JSON.stringify(WEIGHTS)], { maxBuffer: 64 << 20 }).toString());
const read = (f) => fs.readFileSync(path.join(DATA, f), "utf8");
const data = E.loadInputs({ club: read("club_info.csv"), prof: read("prof_info.csv"), lecture: read("lecture_info.csv") });

let bad = 0;
function same(js, pyv, what) {
  const a = JSON.stringify(js), b = JSON.stringify(pyv);
  if (a === b) return;
  bad++;
  if (bad <= 10) console.log(`DIFF ${what}\n  js: ${a.slice(0, 300)}\n  py: ${b.slice(0, 300)}`);
}

same(E.dataIssues(data), py.issues, "data issues");
same(data.columns, py.columns, "columns used");
WEIGHTS.forEach((w, i) => {
  const { plans } = E.runPlans(data, w, Object.keys(E.MODES));
  for (const [key, plan] of Object.entries(plans)) {
    const ref = py.cases[i][key], tag = `weights #${i + 1}, ${key}`;
    for (const k of Object.keys(ref.summary)) {
      const a = plan.summary[k], b = ref.summary[k];
      if (typeof b === "number" ? Math.abs(a - b) > 0.051 : a !== b) same(a, b, `${tag}: summary ${k}`);
    }
    same(plan.matches.map((m) => [m.pair.club.id, m.pair.prof.name, m.suggested_month, m.pair.why()]),
      ref.matches.map((r) => [r[0], r[1], r[3], r[4]]), `${tag}: matches`);
    plan.matches.forEach((m, j) => {
      if (ref.matches[j] && Math.abs(m.pair.score - ref.matches[j][2]) > 0.006) same(m.pair.score, ref.matches[j][2], `${tag}: score for ${m.pair.club.name}`);
    });
    const s = (u, n) => u.suggestions[n] || ["", ""];
    same(plan.unmatched.map((u) => [u.club.id, u.reason, s(u, 0)[0], s(u, 0)[1], s(u, 1)[0], s(u, 2)[0]]), ref.unmatched, `${tag}: unmatched`);
  }
});

if (bad) { console.log(`${bad} differences between the JavaScript and Python engines.`); process.exit(1); }
console.log(`The JavaScript and Python engines agree on every plan (${Object.keys(E.MODES).length} plans x ${WEIGHTS.length} weight settings).`);
