import networkx as nx
from classes import *

def max_weight_matching_nx(matches, professors, clubs):
    """
    Use networkx to find maximum weight bipartite matching.
    """
    # Create bipartite graph
    G = nx.Graph()
    
    # Add nodes with bipartite attribute
    G.add_nodes_from(professors, bipartite=0)
    G.add_nodes_from(clubs, bipartite=1)
    
    # Add edges with weights
    for match in matches:
        G.add_edge(match.prof, match.club, weight=match.score)
    
    # Find maximum weight matching with maximum cardinality
    matching_dict = nx.max_weight_matching(G, maxcardinality=True)
    
    # Convert back to Match objects
    assigned_matches = []   
    for node1, node2 in matching_dict:
        # Figure out which is prof and which is club
        if node1 in professors:
            prof, club = node1, node2
        else:
            prof, club = node2, node1
    
        # Find the original Match object
        match_obj = next(m for m in matches if m.prof == prof and m.club == club)
        assigned_matches.append(match_obj)
    
    print(f"Max-weight matched {len(assigned_matches)} pairs")
    print(f"Total score: {sum(m.score for m in assigned_matches):.1f}")
    
    return assigned_matches