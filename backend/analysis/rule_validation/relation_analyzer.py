"""
relation_analyzer.py
======================
Analyzes and compiles detailed metadata and human-readable summaries
for relations connecting any two nodes in the graph.
"""

import sys
from pathlib import Path

# Ensure packages can be imported correctly regardless of entry point
CURRENT_DIR = Path(__file__).parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(CURRENT_DIR.parent.parent) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR.parent.parent))

from datetime import datetime
from rule_engine import parse_timestamp, normalize_ts
from person_profile_builder import format_event_description
from validate import load_graph, get_entity_name

def get_relation_summary_and_metadata(source_id: str, target_id: str) -> dict:
    """
    Examines all relations between source_id and target_id (in either direction),
    formats their attributes, and builds a comprehensive, human-readable summary.
    """
    graph = load_graph()
    relations = graph.get("relations", [])
    master_entities = graph.get("master_entities", [])
    
    # Build maps
    masters_dict = {m["master_id"]: m for m in master_entities}
    name_map = {m["master_id"]: get_entity_name(m) for m in master_entities}
    
    source_name = name_map.get(source_id, source_id)
    target_name = name_map.get(target_id, target_id)
    
    # Filter matching relations (bidirectional)
    matching_rels = []
    for r in relations:
        src = r["source"]
        tgt = r["target"]
        if (src == source_id and tgt == target_id) or (src == target_id and tgt == source_id):
            matching_rels.append(r)
            
    if not matching_rels:
        return {
            "source_id": source_id,
            "source_name": source_name,
            "target_id": target_id,
            "target_name": target_name,
            "summary": f"No direct relations observed between {source_name} and {target_name}.",
            "interactions_count": 0,
            "relations": []
        }
        
    # Sort matching relations chronologically
    sorted_rels = []
    for r in matching_rels:
        ts = parse_timestamp(r.get("timestamp", ""))
        ts_norm = normalize_ts(ts) if ts else datetime.min
        sorted_rels.append((ts_norm, r))
    sorted_rels.sort(key=lambda x: x[0])
    
    # Extract metadata details
    formatted_relations = []
    counts = {"CALLED": 0, "MESSAGED": 0, "EMAILED": 0, "TRANSFERRED_TO": 0, "LOCATED_AT": 0, "DETECTED": 0}
    total_transfer_amount = 0.0
    
    for ts_norm, r in sorted_rels:
        rel_type = r.get("relation", "")
        if rel_type in counts:
            counts[rel_type] += 1
            
        if rel_type == "TRANSFERRED_TO":
            total_transfer_amount += float(r.get("attributes", {}).get("amount", 0))
            
        formatted_relations.append({
            "source_id": r["source"],
            "source_name": name_map.get(r["source"], r["source"]),
            "target_id": r["target"],
            "target_name": name_map.get(r["target"], r["target"]),
            "type": rel_type,
            "timestamp": r.get("timestamp", ""),
            "confidence": r.get("confidence", 1.0),
            "source_type": r.get("source_type", "unknown"),
            "description": format_event_description(r, name_map),
            "attributes": r.get("attributes", {})
        })
        
    # Build human-readable summary
    summary_parts = []
    if counts["CALLED"] > 0:
        summary_parts.append(f"{counts['CALLED']} phone call(s)")
    if counts["MESSAGED"] > 0:
        summary_parts.append(f"{counts['MESSAGED']} chat message(s)")
    if counts["EMAILED"] > 0:
        summary_parts.append(f"{counts['EMAILED']} email(s)")
    if counts["TRANSFERRED_TO"] > 0:
        summary_parts.append(f"{counts['TRANSFERRED_TO']} transaction(s) totaling Rs.{total_transfer_amount:,}")
    if counts["LOCATED_AT"] > 0 or counts["DETECTED"] > 0:
        summary_parts.append("joint physical co-location / proximity events")
        
    connections_desc = ", ".join(summary_parts) if summary_parts else "indirect links"
    
    summary = (
        f"{source_name} and {target_name} share a strong direct connection "
        f"evidenced by {connections_desc}. "
    )
    
    # Add context on flow direction if there are transfers
    transfers = [r for r in formatted_relations if r["type"] == "TRANSFERRED_TO"]
    if transfers:
        first_tx = transfers[0]
        summary += f"Financial movement initiated from {first_tx['source_name']} to {first_tx['target_name']}."
        
    return {
        "source_id": source_id,
        "source_name": source_name,
        "target_id": target_id,
        "target_name": target_name,
        "summary": summary,
        "interactions_count": len(formatted_relations),
        "relations": formatted_relations
    }
