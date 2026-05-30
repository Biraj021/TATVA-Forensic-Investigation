"""
TATVA — Neo4j Database Helper
=============================
Replaces the redundant neo4j_layer package. Reads directly from db.neo4j_client.
Reconstructs the original unified_graph.json structure from Neo4j AuraDB.
Uses local unified_graph.json for hybrid property enrichment (e.g. resolved_values).
"""

import json
import os
from pathlib import Path
from db.neo4j_client import Neo4jClient

GRAPH_PATH = (
    Path(__file__).parent.parent
    / "Graph_Integration_Layer" / "output" / "unified_graph.json"
)

def is_neo4j_available() -> bool:
    """Check if Neo4j is online and reachable with current credentials."""
    try:
        client = Neo4jClient()
        if client.driver is not None:
            client.close()
            return True
        return False
    except Exception:
        return False

def get_graph_data_from_neo4j() -> dict:
    """
    Connects to Neo4j using Neo4jClient, fetches all nodes and relationships,
    and reconstructs the exact schema structure of unified_graph.json.
    
    Uses local unified_graph.json to enrich missing properties (like resolved_values lists).
    """
    client = Neo4jClient()
    if not client.driver:
        raise RuntimeError("Neo4j driver failed to initialize.")

    # 1. Load local graph for hybrid resolved_values lookup
    resolved_values_map = {}
    if GRAPH_PATH.exists():
        try:
            with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                local_data = json.load(f)
                for ent in local_data.get("master_entities", []):
                    mid = ent.get("master_id")
                    if mid and "resolved_values" in ent:
                        resolved_values_map[mid] = ent["resolved_values"]
        except Exception as e:
            print(f"[db_helper] Warn: Failed to parse local JSON for enrichment: {e}")

    try:
        # 2. Fetch Nodes
        # neo4j_importer labels nodes with the master_type (e.g. PERSON, PLACE) and the dataset name (UnifiedGraph)
        # We query any node that has master_type property set
        node_query = """
        MATCH (n)
        WHERE n.master_type IS NOT NULL OR n.dataset IS NOT NULL
        RETURN n, labels(n) as labels
        """
        node_records = client.execute_read(node_query)
        
        master_entities = []
        for rec in node_records:
            node = rec["n"]
            mid = node.get("id") or node.get("master_id")
            if not mid:
                continue

            # Parse entity_types
            entity_types = []
            if "entity_types" in node:
                try:
                    entity_types = json.loads(node["entity_types"])
                except Exception:
                    entity_types = node["entity_types"]
                    if isinstance(entity_types, str):
                        entity_types = [entity_types]

            # Parse source_entities
            source_entities = []
            if "source_entities" in node:
                try:
                    source_entities = json.loads(node["source_entities"])
                except Exception:
                    source_entities = node["source_entities"]

            # Parse resolved_values (try DB first, then fallback to local enrichment)
            resolved_values = []
            if "resolved_values" in node:
                try:
                    resolved_values = json.loads(node["resolved_values"])
                except Exception:
                    resolved_values = node["resolved_values"]
            
            if not resolved_values and mid in resolved_values_map:
                resolved_values = resolved_values_map[mid]

            # Also try getting other properties that might have been flattened
            master_type = node.get("master_type")
            if not master_type:
                # Fallback to labels
                labels = rec["labels"]
                # Filter out the dataset label to find the entity type
                filtered_labels = [l for l in labels if l not in ["UnifiedGraph", "unified_graph"]]
                master_type = filtered_labels[0] if filtered_labels else "ENTITY"

            master_entities.append({
                "master_id": mid,
                "master_type": master_type,
                "entity_types": entity_types,
                "resolved_values": resolved_values,
                "source_entities": source_entities
            })

        # 3. Fetch Relationships
        rel_query = """
        MATCH (s)-[r]->(t)
        WHERE r.dataset IS NOT NULL OR s.master_type IS NOT NULL
        RETURN s.id as source_id, s.master_id as source_mid, 
               t.id as target_id, t.master_id as target_mid, 
               type(r) as relation, properties(r) as props
        """
        rel_records = client.execute_read(rel_query)
        
        relations = []
        for rec in rel_records:
            source = rec["source_mid"] or rec["source_id"]
            target = rec["target_mid"] or rec["target_id"]
            relation = rec["relation"]
            props = rec["props"] or {}

            # Reconstruct attributes from flat "attr_*" keys
            attributes = {}
            for k, v in props.items():
                if k.startswith("attr_"):
                    orig_key = k[5:]
                    # Try to deserialize JSON values (lists/dicts)
                    if isinstance(v, str) and (v.startswith("{") or v.startswith("[")):
                        try:
                            v = json.loads(v)
                        except Exception:
                            pass
                    attributes[orig_key] = v

            relations.append({
                "source": source,
                "target": target,
                "relation": relation,
                "timestamp": props.get("timestamp", ""),
                "confidence": float(props.get("confidence", 1.0)),
                "source_type": props.get("source_type", ""),
                "attributes": attributes
            })

        print(f"[db_helper] Successfully loaded {len(master_entities)} entities and {len(relations)} relations from Neo4j.")
        return {
            "master_entities": master_entities,
            "relations": relations
        }

    finally:
        client.close()
