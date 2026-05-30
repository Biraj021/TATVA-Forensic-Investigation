# -*- coding: utf-8 -*-
"""
node_relation_extractor.py
Reads all_transcripts.txt, extracts entities (nodes) and relations
from each audio source, and outputs a forensic knowledge graph.

Outputs (in sample_data/):
  - node_relation_graph.json   Full graph (nodes + edges) in standard TATVA format
  - nodes.csv                  Entity list
  - relations.csv              Relation list
"""

import os
import sys
import io
import re
import json
import csv
import uuid

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
        SPACY_AVAILABLE = True
    except OSError:
        nlp = None
        SPACY_AVAILABLE = False
except ImportError:
    nlp = None
    SPACY_AVAILABLE = False


# ─────────────────────────────────────────────
# KNOWN ENTITY CORRECTIONS
# ─────────────────────────────────────────────
CORRECTIONS = {
    "arjan sharma":   "Arjun Sharma",
    "priyameta":      "Priya Mehta",
    "priya":          "Priya Mehta",
    "naah pura":      "Nagpur",
    "kabir":          "Kabir",
    "shadownet":      "ShadowNet",
    "p5 biscuit":     "P5 Biscuit",
}

SPACY_LABEL_MAP = {
    "PERSON":       "PERSON",
    "GPE":          "LOCATION",
    "LOC":          "LOCATION",
    "ORG":          "ORGANIZATION",
    "CARDINAL":     None,
    "DATE":         None,
    "TIME":         "TIME",
}

PHONE_PATTERN = re.compile(
    r'(\+?\d{1,3}[.\-\s]?)?(\(?\d{2,4}\)?[.\-\s]?)(\d{3,5}[.\-\s]?)(\d{4,5})'
)

RELATION_RULES = {
    ("PERSON",       "AUDIO_FILE"):    "SPOKE_IN",
    ("LOCATION",     "AUDIO_FILE"):    "MENTIONED_IN",
    ("ORGANIZATION", "AUDIO_FILE"):    "REFERENCED_IN",
    ("PHONE_NUMBER", "AUDIO_FILE"):    "CONTACT_IN",
    ("TIME",         "AUDIO_FILE"):    "TIMED_IN",
    ("PERSON",       "PERSON"):        "COMMUNICATES_WITH",
    ("PERSON",       "LOCATION"):      "LOCATED_IN",
    ("PERSON",       "ORGANIZATION"):  "AFFILIATED_WITH",
}


def normalize(text):
    return CORRECTIONS.get(text.lower(), text)


def extract_phones(text):
    phones = []
    seen = set()
    for match in PHONE_PATTERN.findall(text):
        raw = "".join(match).strip()
        digits = re.sub(r'\D', '', raw)
        if len(digits) >= 7 and raw not in seen:
            seen.add(raw)
            phones.append(raw)
    return phones


def make_entity(ent_type, text, source, confidence=0.85):
    return {
        "temp_id":    f"ent_{uuid.uuid4().hex[:8]}",
        "type":       ent_type,
        "attributes": {
            "text":       normalize(text),
            "raw_text":   text
        },
        "confidence": confidence,
        "source":     source,
    }


def extract_entities(text, source):
    entities = []
    seen = set()

    if SPACY_AVAILABLE and nlp:
        doc = nlp(text)
        for ent in doc.ents:
            ent_type = SPACY_LABEL_MAP.get(ent.label_)
            if not ent_type:
                continue
            canonical = normalize(ent.text).lower()
            if canonical not in seen:
                seen.add(canonical)
                entities.append(make_entity(ent_type, ent.text, source))
    else:
        print(f"  [WARN] spaCy not available. Using keyword fallback for: {source}")
        known = [
            ("Arjun Sharma",  "PERSON"),
            ("Priya Mehta",   "PERSON"),
            ("Kabir",         "PERSON"),
            ("Mumbai",        "LOCATION"),
            ("New Delhi",     "LOCATION"),
            ("Bhopal",        "LOCATION"),
            ("Nagpur",        "LOCATION"),
            ("CBI",           "ORGANIZATION"),
            ("ShadowNet",     "ORGANIZATION"),
            ("P5 Biscuit",    "ORGANIZATION"),
        ]
        text_lower = text.lower()
        for name, ent_type in known:
            if name.lower() in text_lower:
                key = name.lower()
                if key not in seen:
                    seen.add(key)
                    entities.append(make_entity(ent_type, name, source, confidence=0.99))

    for phone in extract_phones(text):
        if phone not in seen:
            seen.add(phone)
            entities.append(make_entity("PHONE_NUMBER", phone, source, confidence=0.90))

    return entities


def build_relations(entities, audio_node_id):
    relations = []

    for ent in entities:
        rel_key = (ent["type"], "AUDIO_FILE")
        rel_type = RELATION_RULES.get(rel_key, "MENTIONED_IN")
        relations.append({
            "source":      ent["temp_id"],
            "target":      audio_node_id,
            "relation":    rel_type,
            "attributes":  {
                "source_text": ent["attributes"]["text"],
                "target_text": audio_node_id
            },
            "timestamp":   None,
            "confidence":  ent["confidence"],
            "source_type": "audio"
        })

    # Cross-entity relations
    persons = [e for e in entities if e["type"] == "PERSON"]
    locations = [e for e in entities if e["type"] == "LOCATION"]
    orgs = [e for e in entities if e["type"] == "ORGANIZATION"]

    for person in persons:
        for loc in locations:
            relations.append({
                "source":      person["temp_id"],
                "target":      loc["temp_id"],
                "relation":    "LOCATED_IN",
                "attributes":  {
                    "source_text": person["attributes"]["text"],
                    "target_text": loc["attributes"]["text"]
                },
                "timestamp":   None,
                "confidence":  0.75,
                "source_type": "audio"
            })
        for org in orgs:
            relations.append({
                "source":      person["temp_id"],
                "target":      org["temp_id"],
                "relation":    "AFFILIATED_WITH",
                "attributes":  {
                    "source_text": person["attributes"]["text"],
                    "target_text": org["attributes"]["text"]
                },
                "timestamp":   None,
                "confidence":  0.75,
                "source_type": "audio"
            })

    for i, p1 in enumerate(persons):
        for p2 in persons[i+1:]:
            relations.append({
                "source":      p1["temp_id"],
                "target":      p2["temp_id"],
                "relation":    "COMMUNICATES_WITH",
                "attributes":  {
                    "source_text": p1["attributes"]["text"],
                    "target_text": p2["attributes"]["text"]
                },
                "timestamp":   None,
                "confidence":  0.80,
                "source_type": "audio"
            })

    return relations


def parse_all_transcripts(filepath):
    sources = {}
    current_file = None
    lines = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("[") and line.endswith("]"):
                if current_file and lines:
                    sources[current_file] = " ".join(lines).strip()
                current_file = line[1:-1]
                lines = []
            elif line:
                lines.append(line)

    if current_file and lines:
        sources[current_file] = " ".join(lines).strip()

    return sources


def main():
    print("=" * 55)
    print("  Node-Relation Extractor — Forensic Graph Builder")
    print("=" * 55)
    print(f"  spaCy NER: {'ENABLED (en_core_web_sm)' if SPACY_AVAILABLE else 'DISABLED (fallback mode)'}\n")

    base_dir   = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.join(base_dir, "sample_data")
    transcripts_path = os.path.join(sample_dir, "all_transcripts.txt")

    if not os.path.isfile(transcripts_path):
        print(f"[ERROR] all_transcripts.txt not found at: {transcripts_path}")
        sys.exit(1)

    sources = parse_all_transcripts(transcripts_path)
    print(f"  Loaded {len(sources)} transcript(s): {list(sources.keys())}\n")

    all_nodes     = []
    all_relations = []
    all_audio_nodes = []

    for filename, text in sources.items():
        print(f"-- Processing: {filename}")

        audio_node = {
            "temp_id":    f"audio_{uuid.uuid4().hex[:6]}",
            "type":       "AUDIO_FILE",
            "attributes": {
                "text":       filename,
                "raw_text":   filename,
                "transcript": text
            },
            "confidence": 1.0,
            "source":     filename,
        }
        all_audio_nodes.append(audio_node)

        entities = extract_entities(text, filename)
        print(f"   Entities found: {len(entities)}")
        for e in entities:
            print(f"     [{e['type']}] {e['attributes']['text']}")

        relations = build_relations(entities, audio_node["temp_id"])
        print(f"   Relations built: {len(relations)}\n")

        all_nodes.extend(entities)
        all_relations.extend(relations)

    all_nodes.extend(all_audio_nodes)

    # OUTPUT MATCHING TATVA FIR JSON
    output = {
        "entities": all_nodes,
        "relations": all_relations
    }

    json_path = os.path.join(sample_dir, "node_relation_graph.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    print(f"[OK] Saved: node_relation_graph.json")


    print("\n" + "=" * 55)
    print("  GRAPH SUMMARY")
    print("=" * 55)
    print(f"  Total Entities  : {len(output['entities'])}")
    print(f"  Total Relations : {len(output['relations'])}")
    print("=" * 55)

    return output


if __name__ == "__main__":
    main()
