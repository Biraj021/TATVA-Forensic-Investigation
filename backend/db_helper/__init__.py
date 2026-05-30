"""
TATVA — Neo4j Database Helper
=============================
Replaces the redundant neo4j_layer package. Reads directly from db.neo4j_client.
Reconstructs the original unified_graph.json structure from Neo4j AuraDB.
Uses local unified_graph.json for hybrid property enrichment (e.g. resolved_values).
"""