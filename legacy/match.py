# matches.py
import json
import csv
from pathlib import Path

from classes import Match
from parse_csv import load_clubs_from_csv, load_profs_from_csv
from greedy_match import precompute_matches, greedy_matching, export_matches_to_csv
from config import CLUBS_CSV, PROFS_CSV, LECTURES_CSV, WEIGHTS_FILE, OUTPUTS


def _short_why(m: Match) -> str:
    parts = []
    if m.shared_months:
        parts.append(f"months:{len(m.shared_months)}")
    if m.shared_themes:
        parts.append(f"themes:{len(m.shared_themes)}")
    if m.shared_lectures:
        parts.append(f"lectures:{len(m.shared_lectures)}")
    if m.shared_formats:
        parts.append(f"formats:{len(m.shared_formats)}")
    return ", ".join(parts) if parts else "no overlap"


def near_miss_rank(club, prof):
    """
    Rank profs for an unmatched club WITHOUT hard-killing.
    Uses overlaps as a 'closeness' measure (useful when there are zero valid matches).
    """
    m = Match(club, prof)

    months = len(m.shared_months)
    themes = len(m.shared_themes)
    lectures = len(m.shared_lectures)
    formats = len(m.shared_formats)

    # Weighted closeness score (NOT your real match score)
    score = (lectures * 10) + (themes * 5) + (months * 2) + (formats * 1)

    missing = []
    if months == 0:
        missing.append("missing_months")
    if (themes == 0 and lectures == 0):
        missing.append("missing_content")
    if formats == 0:
        missing.append("no_format_match")

    why = f"lect:{lectures}, themes:{themes}, months:{months}, fmt:{formats}"
    if missing:
        why += " | " + ",".join(missing)

    return score, why, m


def export_unmatched_clubs(clubs, profs, assigned_matches, out_path, top_k=3):
    """
    For each unmatched club:
      1) If availability missing -> flag and omit suggestions
      2) Else, list TOP K professors that are TRUE valid matches (shared months + shared themes/lectures)
      3) If there are zero valid matches, fall back to near-miss suggestions (and say so)
    """
    used_clubs = set(m.club for m in assigned_matches)
    unmatched = [c for c in clubs if c not in used_clubs]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        header = ["Club ID", "Club", "Region", "Size", "Engagement Score", "Reason"]
        for i in range(1, top_k + 1):
            header += [
                f"Top {i} Professor",
                f"Top {i} Score",
                f"Top {i} Why",
                f"Top {i} Shared Months",
                f"Top {i} Shared Themes",
                f"Top {i} Shared Lectures",
            ]
        writer.writerow(header)

        for club in unmatched:
            # Missing availability: don't compute suggestions
            if getattr(club, "missing_availability", False):
                reason = "Missing Availability in club_info.csv (fill Availability column) — suggestions omitted"
                row = [
                    getattr(club, "id", ""),
                    club.name,
                    getattr(club, "region", ""),
                    getattr(club, "size", ""),
                    getattr(club, "eg_score", ""),
                    reason,
                ]
                while len(row) < len(header):
                    row += [""] * (len(header) - len(row))
                writer.writerow(row)
                continue

            has_any_months_overlap = False
            has_any_content_overlap = False

            valid = []  # (real_score, why, Match)
            near = []   # (near_score, why, Match)

            for prof in profs:
                m = Match(club, prof)

                if m.shared_months:
                    has_any_months_overlap = True
                if m.shared_themes or m.shared_lectures:
                    has_any_content_overlap = True

                # "True match" criteria mirrors your scoring gate:
                # shared months AND (shared themes OR shared lectures)
                if (len(m.shared_months) > 0) and (len(m.shared_themes) > 0 or len(m.shared_lectures) > 0):
                    valid.append((m.score, _short_why(m), m))
                else:
                    score, why, _ = near_miss_rank(club, prof)
                    near.append((score, why, m))

            # Reason + choose ranking set
            if not has_any_months_overlap:
                reason = "No shared availability months with any professor (months are the blocker)"
            elif not has_any_content_overlap:
                reason = "Some month overlap exists, but no theme/lecture overlap with any professor (content is the blocker)"
            elif valid:
                reason = "Valid matches exist; unmatched due to competition/capacity in greedy assignment"
            else:
                reason = "No valid matches under current rules; showing closest near-miss suggestions"

            ranked = valid if valid else near
            ranked.sort(key=lambda x: x[0], reverse=True)
            top = ranked[:top_k]

            row = [
                getattr(club, "id", ""),
                club.name,
                getattr(club, "region", ""),
                getattr(club, "size", ""),
                getattr(club, "eg_score", ""),
                reason,
            ]

            for score, why, m in top:
                row += [
                    m.prof.name,
                    f"{score:.2f}",
                    why,
                    "; ".join(m.shared_months),
                    "; ".join(m.shared_themes),
                    "; ".join(m.shared_lectures),
                ]

            while len(row) < len(header):
                row += [""] * (len(header) - len(row))

            writer.writerow(row)

    print(f"Exported {len(unmatched)} unmatched clubs (+ top {top_k} suggestions) to {out_path}")


def load_weights(path: Path) -> dict:
    if not path.exists():
        return {"size_weight": None, "eng_weight": None, "title_weight": None}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    allowed = {"size_weight", "eng_weight", "title_weight"}
    return {k: data.get(k) for k in allowed if k in data}


def main():
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    clubs = load_clubs_from_csv(str(CLUBS_CSV))
    profs = load_profs_from_csv(str(PROFS_CSV), str(LECTURES_CSV))
    print(f"Loaded {len(clubs)} clubs and {len(profs)} professors.")

    all_matches = precompute_matches(profs, clubs)
    result = greedy_matching(all_matches)

    out_matches = OUTPUTS / "matches_sheet.csv"
    export_matches_to_csv(result, str(out_matches))

    out_unmatched = OUTPUTS / "unmatched_clubs_sheet.csv"
    export_unmatched_clubs(clubs, profs, result, str(out_unmatched), top_k=3)

    weights = load_weights(WEIGHTS_FILE)
    print(f"\nweights.json loaded from {WEIGHTS_FILE}: {weights}")

    print("\nTop 5 match explanations (default):")
    for match in result[:5]:
        print(match.explanation())
        print()

    print(f"\nDone. Outputs written to:\n- {out_matches}\n- {out_unmatched}")


if __name__ == "__main__":
    main()
