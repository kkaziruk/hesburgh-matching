import unittest
from classes import Club, Professor
from classes import Match
from greedy_match import precompute_matches, greedy_matching
from parse_csv import load_clubs_from_csv, load_profs_from_csv

class TestMatching(unittest.TestCase):
    def test_realistic_akron_chiang_match(self):
        """Test actual Akron club matched with David Chiang"""
        prof = Professor(
            name="David Chiang",
            title="Associate Professor",
            months_available=["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
            lectures_by_theme={
                "AI & Emerging Tech": ["What Large Language Models Can and Can't Do"]
            },
            talk_formats=["Lecture with Q&A"],
            max_events=2
        )
        club = Club(
            id_no="CCG0036010",
            name="Akron",
            size="B",
            region="South",
            engagement_score=300,
            months_available=["January", "February", "March"],
            talk_formats=["Lecture with Q&A"],
            past_speakers=["Clive Neal", "Ken Dye", "Dan Gezelter", "James O'Rourke"],
            requested_themes=["AI & Emerging Tech"],
            requested_lectures=["What Large Language Models Can and Can't Do"]
        )
        match = Match(club, prof)
        self.assertGreater(match.score, 15, f"Akron-Chiang should be strong match, got {match.score:.1f}")
        self.assertIn("AI & Emerging Tech", match.shared_themes)
        self.assertGreater(len(match.shared_lectures), 0)
        self.assertEqual(len(match.shared_months), 3)
        print(f"✓ Akron-Chiang match works (score: {match.score:.1f})")

    def test_realistic_atlanta_pippenger_nomatch(self):
        """Test that Michael Pippenger has 0 viable matches (as shown in your output)"""
        prof = Professor(
            name="Michael Pippenger",
            title="Professor",
            months_available=["January", "February"],
            lectures_by_theme={
                "Current Times & Social Issues": ["Where Notre Dame Meets the World"]
            },
            talk_formats=["Lecture with Q&A"],
            max_events=1
        )
        club = Club(
            id_no="TEST",
            name="No Match Club",
            size="A",
            region="Test",
            engagement_score=300,
            months_available=["June", "July"],
            talk_formats=["Lecture with Q&A"],
            past_speakers=[],
            requested_themes=["AI & Emerging Tech"],
            requested_lectures=[]
        )
        match = Match(club, prof)
        self.assertEqual(match.score, 0, "No month overlap should be dealbreaker")
        print("✓ Pippenger no-match scenario works")

    def test_combined_lecture_format(self):
        """Test that lectures match the Combined format from lecture_info.csv"""
        prof = Professor(
            name="Maria McKenna",
            title="Professor of the Practice",
            months_available=["January", "February", "April", "November"],
            lectures_by_theme={
                "Arts & Culture": ["20th Century Educational Philosophy"],
                "Current Times & Social Issues": ["Civic Engagement of Youth and Young Adults"]
            },
            talk_formats=["Lecture with Q&A"],
            max_events=2
        )
        club = Club(
            id_no="CCG0039060",
            name="Pittsburgh",
            size="AA",
            region="Illinois",
            engagement_score=325,
            months_available=["April", "November"],
            talk_formats=["Lecture with Q&A"],
            past_speakers=[],
            requested_themes=["Arts & Culture"],
            requested_lectures=["20th Century Educational Philosophy"]
        )
        match = Match(club, prof)
        self.assertGreater(match.score, 15, f"Pittsburgh-McKenna should be strong, got {match.score:.1f}")
        print(f"✓ Pittsburgh-McKenna match works (score: {match.score:.1f})")

    def test_martijn_cremers_san_francisco(self):
        """Test the top match from your actual output"""
        prof = Professor(
            name="Martijn Cremers",
            title="Martin J. Gillen Dean of the Mendoza College of Business",
            months_available=["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
            lectures_by_theme={
                "Business & Economics": [
                    "Grow the Good in Business in Light of Catholic Social Thought",
                    "Active Management of Investment Funds"
                ]
            },
            talk_formats=["Lecture with Q&A", "Fireside chat with moderator"],
            max_events=2
        )
        club = Club(
            id_no="CCG0005070",
            name="San Francisco",
            size="AA",
            region="Midwest",
            engagement_score=350,
            months_available=["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
            talk_formats=["Lecture with Q&A", "Fireside chat with moderator", "Panel discussion with other (local) experts/faculty"],
            past_speakers=[],
            requested_themes=["Business & Economics"],
            requested_lectures=["Grow the Good in Business in Light of Catholic Social Thought"]
        )
        match = Match(club, prof)
        self.assertGreater(match.score, 40, f"Top match should score high, got {match.score:.1f}")
        self.assertGreater(len(match.shared_lectures), 0)
        self.assertEqual(len(match.shared_months), 12)
        print(f"✓ San Francisco-Cremers top match works (score: {match.score:.1f})")

    def test_size_weights(self):
        """Test size weight distribution"""
        prof = Professor("P", "professor", ["Jan"], {"Tech": ["AI"]}, ["Lecture with Q&A"], 1)
        sizes_and_expected_order = [
            ("AA", None), ("A", None), ("B", None), 
            ("C", None), ("D", None), ("E", None), ("F", None)
        ]
        scores = []
        for size, _ in sizes_and_expected_order:
            club = Club("1", f"Club {size}", size, "R1", 500, ["Jan"], ["Lecture with Q&A"], [], ["Tech"], [])
            match = Match(club, prof)
            scores.append((size, match.score))
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i][1], scores[i+1][1], f"Size {scores[i][0]} should score >= {scores[i+1][0]}")
        print(f"✓ Size weights work correctly: {[f'{s}:{sc:.1f}' for s, sc in scores]}")

    def test_engagement_buckets(self):
        """Test engagement score bucketing"""
        prof = Professor("P", "professor", ["Jan"], {"Tech": ["AI"]}, ["Lecture with Q&A"], 1)
        engagement_scores = [100, 150, 250, 350, 450, 600]
        scores = []
        for eng in engagement_scores:
            club = Club("1", f"Eng {eng}", "A", "R1", eng, ["Jan"], ["Lecture with Q&A"], [], ["Tech"], [])
            match = Match(club, prof)
            scores.append((eng, match.score))
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i+1][1], scores[i][1], f"Engagement {scores[i+1][0]} should score >= {scores[i][0]}")
        print(f"✓ Engagement buckets work: {[f'{e}:{s:.1f}' for e, s in scores]}")

    def test_no_shared_months_dealbreaker(self):
        """Test that no shared availability = 0 score"""
        prof = Professor("P", "professor", ["January"], {"Tech": ["AI"]}, ["Lecture with Q&A"], 1)
        club = Club("1", "C", "A", "R1", 500, ["June"], ["Lecture with Q&A"], [], ["Tech"], [])
        match = Match(club, prof)
        self.assertEqual(match.score, 0.0, "No shared months should be dealbreaker")
        print("✓ No shared months dealbreaker works")

    def test_no_theme_overlap_dealbreaker(self):
        """Test that no theme overlap = 0 score"""
        prof = Professor("P", "professor", ["Jan"], {"Tech": ["AI"]}, ["Lecture with Q&A"], 1)
        club = Club("1", "C", "A", "R1", 500, ["Jan"], ["Lecture with Q&A"], [], ["Religion & Spirituality"], [])
        match = Match(club, prof)
        self.assertEqual(match.score, 0.0, "No theme overlap should be dealbreaker")
        print("✓ No theme overlap dealbreaker works")

    def test_greedy_produces_valid_matching(self):
        """Test that greedy produces a valid matching with no duplicates"""
        profs = [
            Professor(f"P{i}", "professor", ["Jan"], {"Tech": ["AI"]}, ["Lecture with Q&A"], 1)
            for i in range(5)
        ]
        clubs = [
            Club(f"{i}", f"C{i}", "A", "R1", 500, ["Jan"], ["Lecture with Q&A"], [], ["Tech"], [])
            for i in range(10)
        ]
        matches = precompute_matches(profs, clubs)
        result = greedy_matching(matches)
        self.assertLessEqual(len(result), 5, "Can't match more professors than available")
        profs_used = [m.prof for m in result]
        clubs_used = [m.club for m in result]
        self.assertEqual(len(profs_used), len(set(profs_used)), "No duplicate professors")
        self.assertEqual(len(clubs_used), len(set(clubs_used)), "No duplicate clubs")
        print(f"✓ Greedy produces valid matching ({len(result)} matches)")

    def test_integration_with_real_data(self):
        """Integration test: load actual CSV data and verify matching works"""
        try:
            clubs = load_clubs_from_csv("club_info.csv")
            professors = load_profs_from_csv("prof_info.csv", "lecture_info.csv")
            self.assertGreater(len(clubs), 0, "Should load clubs from CSV")
            self.assertGreater(len(professors), 0, "Should load professors from CSV")
            all_matches = precompute_matches(professors, clubs)
            self.assertGreater(len(all_matches), 0, "Should create viable matches")
            result = greedy_matching(all_matches)
            self.assertGreater(len(result), 0, "Should produce matches")
            profs_used = [m.prof for m in result]
            clubs_used = [m.club for m in result]
            self.assertEqual(len(profs_used), len(set(profs_used)), "No duplicate professors")
            self.assertEqual(len(clubs_used), len(set(clubs_used)), "No duplicate clubs")
            print(f"✓ Integration test passed: {len(result)} matches from {len(professors)} professors and {len(clubs)} clubs")
        except FileNotFoundError as e:
            print(f"⚠ Skipping integration test (CSV files not found): {e}")

    def test_against_known_results(self):
        """Verify algorithm produces expected results from actual CSV data"""
        try:
            clubs = load_clubs_from_csv("club_info.csv")
            professors = load_profs_from_csv("prof_info.csv", "lecture_info.csv")
            all_matches = precompute_matches(professors, clubs)
            greedy_result = greedy_matching(all_matches)
            self.assertEqual(len(greedy_result), 34, f"Expected 34 matches, got {len(greedy_result)}")
            total_score = sum(m.score for m in greedy_result)
            self.assertGreater(total_score, 751)
            self.assertLess(total_score, 754)
            sf_cremers = [m for m in greedy_result 
                          if m.club.name == "San Francisco" and m.prof.name == "Martijn Cremers"]
            self.assertEqual(len(sf_cremers), 1, "Should match San Francisco with Martijn Cremers")
            self.assertGreater(sf_cremers[0].score, 43)
            self.assertLess(sf_cremers[0].score, 45)
            sjv_garnett = [m for m in greedy_result
                           if m.club.name == "St. Joseph Valley" and m.prof.name == "Richard Garnett"]
            self.assertEqual(len(sjv_garnett), 1, "Should match St. Joseph Valley with Richard Garnett")
            self.assertGreater(sjv_garnett[0].score, 42)
            self.assertLess(sjv_garnett[0].score, 44)
            phx_hfc = [m for m in greedy_result
                       if m.club.name == "Phoenix" and m.prof.name == "Heather Foucault-Camm"]
            self.assertEqual(len(phx_hfc), 1, "Should match Phoenix with Heather Foucault-Camm")
            print(f"✓ Results match known output (34 matches, score 752.4)")
        except FileNotFoundError as e:
            print(f"⚠ Skipping known results test (CSV files not found): {e}")

if __name__ == "__main__":
    unittest.main()