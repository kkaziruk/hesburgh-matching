import time
from parse_csv import load_clubs_from_csv, load_profs_from_csv
from greedy_match import precompute_matches, greedy_matching
from mw_match import max_weight_matching_nx

print("="*60)
print("PROFESSOR-CLUB MATCHING SYSTEM")
print("="*60)

# Load full dataset
clubs = load_clubs_from_csv("club_info.csv")
professors = load_profs_from_csv("prof_info.csv", "lecture_info.csv")
print(f'\nLoaded {len(clubs)} clubs and {len(professors)} professors.')

# ============================================================
# FULL DATASET ANALYSIS
# ============================================================
print("\n" + "="*60)
print("FULL DATASET (52 clubs, 40 professors)")
print("="*60)

all_matches = precompute_matches(professors, clubs)

# Time greedy
start = time.time()
greedy_result = greedy_matching(all_matches)
greedy_time = time.time() - start

# Time networkx
start = time.time()
max_weight_result = max_weight_matching_nx(all_matches, professors, clubs)
nx_time = time.time() - start

print(f"\n--- Timing Results (Full Dataset) ---")
print(f"Greedy time:     {greedy_time:.6f}s")
print(f"NetworkX time:   {nx_time:.6f}s")
print(f"Speedup:         {nx_time/greedy_time:.1f}x (greedy is faster)")

print(f"\n--- Quality Results (Full Dataset) ---")
greedy_score = sum(m.score for m in greedy_result)
nx_score = sum(m.score for m in max_weight_result)
print(f"Greedy:      {len(greedy_result)} matches, total score = {greedy_score:.1f}")
print(f"NetworkX:    {len(max_weight_result)} matches, total score = {nx_score:.1f}")
print(f"Improvement: {((nx_score - greedy_score) / greedy_score * 100):.1f}% better score")
print(f"             {len(max_weight_result) - len(greedy_result)} more matches")

# ============================================================
# SMALLER DATASET ANALYSIS
# ============================================================
print("\n" + "="*60)
print("SMALLER DATASET (25 clubs, 20 professors)")
print("="*60)

small_clubs = clubs[:25]
small_profs = professors[:20]
small_matches = precompute_matches(small_profs, small_clubs)

# Time greedy on small dataset
start = time.time()
small_greedy = greedy_matching(small_matches)
small_greedy_time = time.time() - start

# Time networkx on small dataset
start = time.time()
small_nx = max_weight_matching_nx(small_matches, small_profs, small_clubs)
small_nx_time = time.time() - start

print(f"\n--- Timing Results (Small Dataset) ---")
print(f"Greedy time:     {small_greedy_time:.6f}s")
print(f"NetworkX time:   {small_nx_time:.6f}s")
print(f"Speedup:         {small_nx_time/small_greedy_time:.1f}x (greedy is faster)")

print(f"\n--- Quality Results (Small Dataset) ---")
small_greedy_score = sum(m.score for m in small_greedy)
small_nx_score = sum(m.score for m in small_nx)
print(f"Greedy:      {len(small_greedy)} matches, total score = {small_greedy_score:.1f}")
print(f"NetworkX:    {len(small_nx)} matches, total score = {small_nx_score:.1f}")

# ============================================================
# TIMING COMPARISON
# ============================================================
print("\n" + "="*60)
print("TIMING COMPARISON ACROSS DATASET SIZES")
print("="*60)
print(f"\nDataset Size | Greedy Time | NetworkX Time | Speedup")
print(f"-------------|-------------|---------------|--------")
print(f"Small (25x20)|  {small_greedy_time:.6f}s |   {small_nx_time:.6f}s   |  {small_nx_time/small_greedy_time:.1f}x")
print(f"Full (52x40) |  {greedy_time:.6f}s |   {nx_time:.6f}s   |  {nx_time/greedy_time:.1f}x")

# ============================================================
# TOP MATCHES
# ============================================================
print("\n" + "="*60)
print("TOP 5 MATCHES (Full Dataset - Greedy)")
print("="*60)
for i, match in enumerate(sorted(greedy_result, key=lambda m: m.score, reverse=True)[:5], 1):
    print(f"{i}. {match.club.name} ↔ {match.prof.name}")
    print(f"   Score: {match.score:.2f}")
    print(f"   Themes: {', '.join(match.shared_themes)}")
    print(f"   Months overlap: {len(match.shared_months)}")
    print()

print("="*60)
print("ANALYSIS COMPLETE")
print("="*60)