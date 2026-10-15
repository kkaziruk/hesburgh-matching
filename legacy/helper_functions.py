import csv
from collections import defaultdict

ALL_MONTHS = [ "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTH_INDEX = {m: i for i, m in enumerate(ALL_MONTHS)}
ALL_TITLES = [
    "provost", 
    "vice president", 
    "dean",  
    "program director",
    "director",   
    "associate professor", 
    "professor of the practice",
    "teaching professor",
    "assistant professor",
    "professor",
    ]
TITLE_WEIGHTS = {
    "provost": 1.30,
    "vice president": 1.25,
    "dean": 1.20,
    "director": 1.15,
    "program director": 1.10,
    "associate professor": 1.05,
    "professor of the practice": 1.02,
    "teaching professor": 1.00,  
    "assistant professor": 1.00,
    "professor": 1.00,
}

SIZE_WEIGHTS = {
    "AA": 1.00,
    "A":  0.90,
    "B":  0.80,
    "C":  0.70,
    "D":  0.60,
    "E":  0.50,
    "F":  0.40,
}

def normalize_title(raw_title):
    best = (len(ALL_TITLES) + 1, "professor")  

    if not raw_title:
        return best[1]

    raw = raw_title.lower()

    for i, t in enumerate(ALL_TITLES):
        if t in raw and i < best[0]:
            best = (i, t)

    return best[1]

def parse_theme_and_title(cell):
    # Return (theme, lecture_title) from a Theme cell
    if not cell or "|" not in cell:
        return None, None

    theme_part, rest = cell.split("|", 1)
    theme = theme_part.strip()

    # rest looks like "Decoding AI- February-March,October-November"
    if "-" in rest:
        title_part = rest.split("-", 1)[0]
        lecture_title = title_part.strip()
    else:
        lecture_title = rest.strip()

    if not theme:
        theme = None
    if not lecture_title:
        lecture_title = None

    return theme, lecture_title

def build_lectures_by_faculty(path2):
    lectures_by_faculty = defaultdict(lambda: defaultdict(list))

    with open(path2, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            faculty = row.get("Faculty", "").strip().lower()
            theme   = row.get("Theme", "").strip()
            topic   = row.get("Topic", "").strip()

            if not faculty or not theme or not topic:
                continue
            if topic not in lectures_by_faculty[faculty][theme]:
                lectures_by_faculty[faculty][theme].append(topic)
                
    return lectures_by_faculty