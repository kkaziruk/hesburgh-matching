"""Builds hesburgh_matcher.html: page_template.html + engine.js + the 2026 sample files.

The sample keeps only the columns the matcher reads (no emails, phones or addresses).
Run: python3 build_page.py              (private page with the 2026 sample)
     python3 build_page.py --no-sample  (index.html, no data, for the repository)
"""
import csv, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The 2026 CSVs: next to web/ in the repository, or two levels up in the project folder.
DATA = next((d for d in (os.path.dirname(HERE), os.path.dirname(os.path.dirname(HERE)))
             if os.path.exists(os.path.join(d, "club_info.csv"))), os.path.dirname(HERE))
KEEP = {
    "club": ("club_info.csv", ["ID Number", "Invited 2026", "Club Check", "Size", "Region", "HLS Score",
                                "2025 Speaker", "2024 Speaker", "2023 Speaker", "2022 Speaker", "Format",
                                "Availability", "Comments", "Theme 1", "Theme 2", "Theme 3", "Theme 4", "Theme 5", "2026 Assignment"]),
    "prof": ("prof_info.csv", ["Participate in the Hesburgh Lecture program in 2026?", "Recipient Full Name",
                                "# of Events", "Title", "Availability", "Format(s)",
                                "Particular clubs or areas of the country you are interested in traveling?"]),
    "lecture": ("lecture_info.csv", ["Theme", "Topic", "Faculty", "Availability"]),
}


def trimmed(path, cols):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        r = {k.strip(): v for k, v in r.items() if k}
        w.writerow([r.get(c, "") for c in cols])
    return out.getvalue()


def build(out, with_sample=True):
    sample = {k: trimmed(os.path.join(DATA, f), cols) for k, (f, cols) in KEEP.items()} if with_sample else None
    page = open(os.path.join(HERE, "page_template.html"), encoding="utf-8").read()
    engine = open(os.path.join(HERE, "engine.js"), encoding="utf-8").read()
    blob = json.dumps(sample).replace("</", "<\\/")
    states = open(os.path.join(HERE, "us_states.json"), encoding="utf-8").read().strip()
    page = page.replace("/*ENGINE*/", engine).replace("/*SAMPLE*/", blob).replace("/*STATES*/", states)
    if not with_sample:
        # A plain web page (GitHub Pages) needs its own document skeleton; the artifact host adds one.
        page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                + page.replace("<style>", "<style>\nhtml, body { margin: 0; height: 100%; }\n", 1).replace("</style>", "</style>\n</head>\n<body>", 1)
                + "\n</body>\n</html>\n")
    open(out, "w", encoding="utf-8").write(page)
    print(f"wrote {out} ({len(page) // 1024} KB)")


if __name__ == "__main__":
    # --no-sample leaves the 2026 files out, for the public copy (index.html in the repository).
    if "--no-sample" in sys.argv:
        build(sys.argv[sys.argv.index("--no-sample") + 1] if len(sys.argv) > sys.argv.index("--no-sample") + 1 else os.path.join(HERE, "index.html"), False)
    else:
        build(os.path.join(HERE, "hesburgh_matcher.html"))
