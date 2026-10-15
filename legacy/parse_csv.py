import re
from classes import *
from helper_functions import *

def load_clubs_from_csv(path):
    clubs = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            
            invited_status = row.get("Invited 2026", "").strip()
            theme1_raw = row.get("Theme 1", "").strip()
            # Include if:
            # - they are invited, OR
            # - they submitted at least one theme
            if not (invited_status == "Invited" or theme1_raw):
                continue

            # # Logistical information: ID, name, size, region, engagement score
            id_no = row["ID Number"].strip()
            if not id_no:
                continue  
            name = row["Club Check"].strip()
            size = row["Size"].strip()
            region = row["Region"].strip()
            engagement_score = int(row["HLS Score"].strip())
            
            avail_raw = row.get("Availability", "") # Availability: "January,February,March"
            months_available = [m.strip() for m in avail_raw.split(",") if m.strip()]
            missing_availability = (len(months_available) == 0)
            
            format_raw = row.get("Format", "") # Format: "Lecture with Q&A" (sometimes multiple, comma-separated)
            talk_formats = [fmt.strip() for fmt in format_raw.split(",") if fmt.strip()]

            requested_themes = [] # Requested themes: Theme 1–Theme 5
            requested_lectures = [] # Requested lectures: Lecture 1-Lecture 5

            for i in range(1, 6):
                raw = row.get(f"Theme {i}", "")
                theme, lecture_title = parse_theme_and_title(raw)
                # themes: unique list (since there may be repetiton)
                if theme and theme not in requested_themes:
                    requested_themes.append(theme)
                if lecture_title:
                    requested_lectures.append(lecture_title)

            past_speakers = [] # Past speakers: 2025–2022
            for col in ["2025 Speaker", "2024 Speaker", "2023 Speaker", "2022 Speaker"]:
                val = row.get(col, "").strip()
                if val:
                    past_speakers.append(val)

            club = Club(id_no, name, size, region, engagement_score, months_available, talk_formats, past_speakers, requested_themes,requested_lectures)
            club.missing_availability = missing_availability
            clubs.append(club)

    return clubs

def load_profs_from_csv(path1, path2):
    profs = []
    lectures_by_faculty = build_lectures_by_faculty(path2)

    with open(path1, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # skipping the second row
        for i, row in enumerate(reader):
            if i == 0:
                continue

            participate = row.get("Participate in the Hesburgh Lecture program in 2026?", "").strip()
            if participate.lower().startswith("no"):
                continue

            # Logistical information
            name = row["Recipient Full Name"].strip()
            title_raw = row.get("Title", "").strip()
            title = normalize_title(title_raw)

            # Availability: "January,February,March" or "All of the above"
            avail_raw = row.get("Availability", "").strip()
            if "all of the above" in avail_raw.lower():
                months_available = ALL_MONTHS.copy()   
            else:
                months_available = [m.strip() for m in avail_raw.split(",") if m.strip()]

            # Max events: "Extract first integer"
            mevents_raw = row.get("# of Events", "")
            match = re.search(r"\d+", mevents_raw) 
            max_events = int(match.group()) if match else 1

            # Talk details
            lectures_by_theme = lectures_by_faculty.get(name.lower(), {})
            format_raw = row.get("Format(s)", "")
            talk_formats = [fmt.strip() for fmt in format_raw.split(",") if fmt.strip()]

            prof = Professor(name, title, months_available, lectures_by_theme, talk_formats, max_events)
            profs.append(prof)

    return profs
