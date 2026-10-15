from classes import *
import csv
import networkx as nx
import matplotlib.pyplot as plt
from collections import Counter

# ============================================================
# 1. PRE-COMPUTE ALL MATCHES
# ============================================================

def precompute_matches(professors, clubs):
    """
    Create Match objects for all professor-club pairs.
    Only keeps matches with score > 0.
    """
    all_matches = []
    
    for prof in professors:
        for club in clubs:
            match = Match(club, prof)
            if match.score > 0:
                all_matches.append(match)
    
    print(f"Pre-computed {len(all_matches)} viable matches")
    return all_matches


# ============================================================
# 2. GREEDY ALGORITHM
# ============================================================

from collections import defaultdict

def greedy_matching(matches, custom_weights=None):
    """
    Greedy algorithm: pick highest-score match, remove the club, and decrement professor capacity.
    Optionally accepts custom_weights dict to override size, engagement, or title weights.
    Returns: assigned_matches
    """

    # Re-score if custom weights provided
    if custom_weights:
        for m in matches:
            m.score = m._calculate_score(**custom_weights)

    sorted_matches = sorted(matches, key=lambda m: m.score, reverse=True)

    assigned_matches = []
    used_clubs = set()

    # Track how many events each professor has been assigned
    prof_counts = defaultdict(int)

    for match in sorted_matches:
        prof = match.prof
        club = match.club

        # Club can only be matched once
        if club in used_clubs:
            continue

        # Professor can be matched up to prof.max_events (default 1)
        max_events = getattr(prof, "max_events", 1) or 1
        if prof_counts[prof] >= max_events:
            continue

        assigned_matches.append(match)
        used_clubs.add(club)
        prof_counts[prof] += 1

    print(f"Greedy matched {len(assigned_matches)} pairs")
    print(f"Total score: {sum(m.score for m in assigned_matches):.1f}")

    # Optional: print capacity usage summary (handy in demos)
    used_profs = sum(1 for p, c in prof_counts.items() if c > 0)
    print(f"Professors used: {used_profs} / {len(set(m.prof for m in matches))}")

    return assigned_matches

def visualize_matches(matches, filename=None):
    """
    Visualize the matches as a bipartite graph using networkx and matplotlib.
    If filename is provided, saves the plot to that file.
    """
    G = nx.Graph()
    prof_nodes = set(m.prof.name for m in matches)
    club_nodes = set(m.club.name for m in matches)
    G.add_nodes_from(prof_nodes, bipartite=0)
    G.add_nodes_from(club_nodes, bipartite=1)
    edges = [(m.prof.name, m.club.name, m.score) for m in matches]
    G.add_weighted_edges_from(edges)
    # Use spring layout for better separation
    pos = nx.spring_layout(G, k=2, seed=42)
    plt.figure(figsize=(14, 9))
    # Draw nodes with different shapes and colors
    nx.draw_networkx_nodes(G, pos, nodelist=prof_nodes, node_color="#457b9d", node_shape="o", node_size=900, label="Professors")
    nx.draw_networkx_nodes(G, pos, nodelist=club_nodes, node_color="#f4a261", node_shape="s", node_size=900, label="Clubs")
    # Draw edges with width proportional to score
    edge_list = [(m.prof.name, m.club.name) for m in matches]
    edge_weights = [m.score for m in matches]
    max_weight = max(edge_weights) if edge_weights else 1
    min_width, max_width = 1, 8
    edge_widths = [min_width + (max_width - min_width) * (w / max_weight) for w in edge_weights]
    nx.draw_networkx_edges(G, pos, edgelist=edge_list, width=edge_widths, alpha=0.7, edge_color="#264653")
    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=11, font_weight="bold", font_color="#222222")
    # Edge labels (scores), offset to avoid overlap
    label_pos = {}
    for (u, v) in edge_list:
        if u in pos and v in pos:
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            label_pos[(u, v)] = ((x1 + x2) / 2, (y1 + y2) / 2 + 0.08)
    labels = {(m.prof.name, m.club.name): f"{m.score:.1f}" for m in matches if m.prof.name in pos and m.club.name in pos}
    nx.draw_networkx_edge_labels(G, label_pos, edge_labels=labels, font_color="#e76f51", font_size=10)
    # Legend and title
    plt.legend(scatterpoints=1, loc="upper left", fontsize=12)
    plt.title("Professor-Club Matches (Bipartite Graph)", fontsize=18, fontweight="bold", color="#264653")
    plt.axis("off")
    plt.tight_layout()
    if filename:
        plt.savefig(filename, bbox_inches="tight", dpi=200)
    else:
        plt.show()

def export_matches_to_csv(matches, path):
    """
    Export assigned matches with explainability columns.
    """
    prof_counts = Counter(m.prof for m in matches)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "Club ID",
            "Club",
            "Region",
            "Size",
            "Engagement Score",
            "Professor",
            "Professor Title",
            "Professor Max Events",
            "Professor Assigned Count",
            "Score",
            "Shared Themes",
            "Shared Lectures",
            "Shared Months",
            "Shared Formats",
        ])

        for m in matches:
            writer.writerow([
                getattr(m.club, "id", ""),
                m.club.name,
                getattr(m.club, "region", ""),
                getattr(m.club, "size", ""),
                getattr(m.club, "eg_score", ""),
                m.prof.name,
                getattr(m.prof, "title", ""),
                getattr(m.prof, "max_events", 1),
                prof_counts[m.prof],
                f"{m.score:.2f}",
                "; ".join(m.shared_themes),
                "; ".join(m.shared_lectures),
                "; ".join(m.shared_months),
                "; ".join(m.shared_formats),
            ])

    print(f"Exported {len(matches)} matches to {path}")
