from helper_functions import *

class Professor:
    def __init__(self, name: str, title: str, months_available: list[str], lectures_by_theme: dict[str, list[str]], talk_formats: list[str], max_events: int=1): 
        self.name = name
        self.title = title
        self.months_avail = months_available or []
        self.max_events = max_events

        # { theme: [lecture_title1, lecture_title2, ...] }
        self.lectures = lectures_by_theme or {}

        # List of themes (just the keys of the dict)
        self.themes = list(self.lectures.keys())

         # Formats like "Lecture", "Fireside Chat", "Q&A", etc.
        self.talk_formats = talk_formats or []

    def report(self):
        print(f"--- Professor Report: {self.name} ---")
        print(f"Title: {self.title}")
        print(f"Max Events: {self.max_events}")
        print(f"Availability: {self.months_avail}")
        print(f"Talk Formats: {self.talk_formats}")
        print(f"Themes Offered: {self.themes}")
        print("Lectures by Theme:")
        if not self.lectures:
            print("  (No lectures recorded)")
        else:
            for theme, lecture_list in self.lectures.items():
                print(f"  - {theme}:")
                for lec in lecture_list:
                    print(f"      • {lec}")
        print("-------------------------------\n")

class Club:
    def __init__(self, id_no: str, name: str, size: str, region: str, engagement_score: int, months_available: list[str], talk_formats: list[str], past_speakers: list[str], requested_themes: list[str], requested_lectures: list[str]):
        # Logistical information
        self.id = id_no
        self.name = name
        self.size = size
        self.region = region
        self.eg_score = engagement_score

        # Availability - months
        self.months_avail = months_available

        # Talk/Lecture information
        self.talk_formats = talk_formats or []
        self.requested_themes = requested_themes or []
        self.requested_lectures = requested_lectures or []
        
        # History
        self.past_speakers = past_speakers or []

    def report(self):
        print(f"--- Club Report: {self.name} ---")
        print(f"ID: {self.id}")
        print(f"Size: {self.size}")
        print(f"Region: {self.region}")
        print(f"Engagement Score: {self.eg_score}")
        print(f"Availability: {self.months_avail}")
        print(f"Talk Formats: {self.talk_formats}")
        print(f"Requested Themes: {self.requested_themes}")
        print(f"Requested Lectures: {self.requested_lectures}")
        print(f"Past Speakers: {self.past_speakers}")
        print("-------------------------------\n")

class Match:
    def __init__(self, club: Club, prof: Professor):
        self.club = club
        self.prof = prof
        self.shared_months = self._check_months()
        self.shared_themes = self._check_themes()
        self.shared_lectures = self._check_lectures()
        self.shared_formats = self._check_formats()
        self.score = self._calculate_score()

    def _check_months(self):
        club_avail = self.club.months_avail
        prof_avail = self.prof.months_avail
        if not club_avail or not prof_avail:
            return []
        return [m for m in club_avail if m in prof_avail]
    
    def _check_themes(self):
        club_themes = self.club.requested_themes
        prof_themes = self.prof.themes
        if not club_themes or not prof_themes:
            return []
        return [m for m in club_themes if m in prof_themes]
    
    def _check_lectures(self):
        shared_themes = self.shared_themes  # list of overlapping themes
        if not shared_themes:
            return []
        
        club_lectures = self.club.requested_lectures      # list of lecture names or empty
        prof_lectures = self.prof.lectures               # dict: theme -> [lecture_title, ...]

        matches = []

        for theme, lecture_list in prof_lectures.items():
            if theme not in shared_themes:
                continue

            # If club didn't specify lectures, count all lectures under overlapping themes
            if not club_lectures:
                for lecture in lecture_list:
                    matches.append(lecture)
                continue

            # If club did specify lectures, only keep those explicitly requested
            for lecture in lecture_list:
                if lecture in club_lectures:
                    matches.append(lecture)

        return matches

    def _check_formats(self):
        club_formats = self.club.talk_formats
        prof_formats = self.prof.talk_formats
        if not club_formats or not prof_formats:
            return []
        return [m for m in club_formats if m in prof_formats]
    
    def _title_weight(self) -> float:
        title = (self.prof.title or "").lower()
        for phrase in sorted(TITLE_WEIGHTS.keys(), key=len, reverse=True):
            if phrase in title:
                return TITLE_WEIGHTS[phrase]
        return 1.0
    
    def _size_weight(self):
        size_code = self.club.size
        if size_code is None:
            return 0.50  # midpoint fallback
        size_code = size_code.strip().upper()
        return SIZE_WEIGHTS[size_code]
    
    def _eng_bucket(self):
        eg_score = self.club.eg_score
        if eg_score is None:
            return 0.5

        if eg_score >= 600:
            return 1.00
        elif eg_score >= 450:
            return 0.90
        elif eg_score >= 350:
            return 0.80
        elif eg_score >= 250:
            return 0.70
        elif eg_score >= 150:
            return 0.60
        else:
            return 0.55

    def _club_priority_score(self):
        size_component = self._size_weight()
        eng_component = self._eng_bucket()
        return 0.65 * size_component + 0.35 * eng_component

    def _calculate_score(self, size_weight=None, eng_weight=None, title_weight=None):
        # Dealbreaker: no shared availability
        if not self.shared_months:
            return 0.0

        lecture_score = len(self.shared_lectures) * 10
        theme_score   = len(self.shared_themes) * 5
        month_score   = len(self.shared_months) * 2
        format_score  = len(self.shared_formats) * 1

        base_score = lecture_score + theme_score + month_score + format_score

        # If only months/formats match (no themes/lectures), kill it
        if lecture_score == 0 and theme_score == 0:
            return 0.0

        # Allow user to override weights
        size_component = size_weight if size_weight is not None else self._size_weight()
        eng_component = eng_weight if eng_weight is not None else self._eng_bucket()
        priority = 0.65 * size_component + 0.35 * eng_component

        # Only boost title for high-engagement clubs
        if priority >= 0.7:
            title_mult = title_weight if title_weight is not None else self._title_weight()
        else:
            title_mult = 1.0

        return base_score * title_mult * priority
    
    def report(self):
        print(f"\n=== MATCH: {self.club.name}  ⇄  {self.prof.name} ===")
        print(f"Score: {self.score:.2f}")

        #print("Themes:",   ", ".join(self.shared_themes)   if self.shared_themes   else "None")
        #print("Lectures:", ", ".join(self.shared_lectures) if self.shared_lectures else "None")
        #print("Months:",   ", ".join(self.shared_months)   if self.shared_months   else "None")
        #print("Formats:",  ", ".join(self.shared_formats)  if self.shared_formats  else "None")

    def explanation(self):
        """
        Return a human-readable explanation for why this match was made.
        """
        lines = [
            f"Match between Professor '{self.prof.name}' and Club '{self.club.name}':",
            f"  - Shared themes: {', '.join(self.shared_themes) if self.shared_themes else 'None'}",
            f"  - Shared lectures: {', '.join(self.shared_lectures) if self.shared_lectures else 'None'}",
            f"  - Shared months: {', '.join(self.shared_months) if self.shared_months else 'None'}",
            f"  - Shared formats: {', '.join(self.shared_formats) if self.shared_formats else 'None'}",
            f"  - Club size: {self.club.size}, Engagement: {self.club.eg_score}",
            f"  - Professor title: {self.prof.title}",
            f"  - Final score: {self.score:.2f}"
        ]
        return '\n'.join(lines)
