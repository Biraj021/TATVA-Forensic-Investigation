"""
Persist and verify TATVA processed/cache artifacts in Upstash Redis.

Supabase/PostgreSQL remains for user-driven data only: cases, notes,
evidence metadata, query logs, and audit logs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent.parent
REDIS_INDEX_KEY = "artifact:index"


@dataclass(frozen=True)
class ArtifactDefinition:
    artifact_name: str
    artifact_type: str
    cache_layer: str
    relative_path: str
    required: bool = True


PROCESSED_INPUT_ARTIFACTS = [
    ArtifactDefinition(
        "fir_processed_graph.json",
        "processed_input",
        "processed_inputs",
        "preprocessor/FIR_Preprocessed/graph_objects.json",
    ),
    ArtifactDefinition(
        "bank_nodes.json",
        "processed_input",
        "processed_inputs",
        "preprocessor/bank_transaction_pipeline/data/processed/nodes.json",
    ),
    ArtifactDefinition(
        "bank_edges.json",
        "processed_input",
        "processed_inputs",
        "preprocessor/bank_transaction_pipeline/data/processed/edges.json",
    ),
    ArtifactDefinition(
        "bank_suspicious_transactions.json",
        "processed_input",
        "processed_inputs",
        "preprocessor/bank_transaction_pipeline/data/processed/suspicious_transactions.json",
    ),
    ArtifactDefinition(
        "vehicle_processed_graph.json",
        "processed_input",
        "processed_inputs",
        "preprocessor/Vehicle_License_preprocessed/forensic_graph.json",
    ),
    ArtifactDefinition(
        "audio_processed_graph.json",
        "processed_input",
        "processed_inputs",
        "preprocessor/audio/outputs/audio_graph.json",
    ),
]


LAYER_1_ARTIFACTS = [
    ArtifactDefinition(
        "all_processed.json",
        "cache",
        "layer_1",
        "Graph_Integration_Layer/output/all_preprocessed_graphs.json",
    ),
    ArtifactDefinition(
        "geo_cache.json",
        "cache",
        "layer_1",
        "Graph_Integration_Layer/output/geo_cache.json",
    ),
    ArtifactDefinition(
        "unified_graph.json",
        "cache",
        "layer_1",
        "Graph_Integration_Layer/output/unified_graph.json",
    ),
]


LAYER_2_ARTIFACTS = [
    ArtifactDefinition(
        "summary.json",
        "cache",
        "layer_2",
        "analysis/graph_summary/summary.json",
    ),
    ArtifactDefinition(
        "flags.json",
        "cache",
        "layer_2",
        "analysis/rule_validation/flags.json",
    ),
    ArtifactDefinition(
        "timeline.json",
        "cache",
        "layer_2",
        "analysis/timeline_reconstruction/timeline.json",
    ),
]


ALL_ARTIFACTS = [
    *PROCESSED_INPUT_ARTIFACTS,
    *LAYER_1_ARTIFACTS,
    *LAYER_2_ARTIFACTS,
]


def artifact_key(cache_layer: str, artifact_name: str) -> str:
    return f"artifact:{cache_layer}:{artifact_name}"


def _artifact_path(definition: ArtifactDefinition) -> Path:
    return BACKEND_DIR / definition.relative_path


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _count_records(content: Any) -> int:
    if isinstance(content, list):
        return len(content)
    if isinstance(content, dict):
        if "entities" in content or "relations" in content:
            return len(content.get("entities", [])) + len(content.get("relations", []))
        if "master_entities" in content or "relations" in content:
            return len(content.get("master_entities", [])) + len(content.get("relations", []))
        if "scenes" in content:
            return len(content.get("scenes", []))
        if "flags" in content and isinstance(content["flags"], dict):
            return sum(len(v) for v in content["flags"].values() if isinstance(v, list))
        return len(content)
    return 0


def build_local_artifact(definition: ArtifactDefinition) -> dict:
    """Read a local artifact and convert it into a Redis-ready payload."""
    path = _artifact_path(definition)
    content = _load_json(path)
    raw = path.read_bytes()
    stat = path.stat()

    return {
        "artifact_name": definition.artifact_name,
        "artifact_type": definition.artifact_type,
        "cache_layer": definition.cache_layer,
        "source_path": str(path),
        "content_json": content,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "record_count": _count_records(content),
        "status": "cached",
        "metadata": {
            "required": definition.required,
            "local_mtime": stat.st_mtime,
            "relative_path": definition.relative_path,
        },
    }


def inspect_local_artifacts() -> list[dict]:
    """Return local availability/hash status for every expected artifact."""
    results = []
    for definition in ALL_ARTIFACTS:
        path = _artifact_path(definition)
        item = {
            "artifact_name": definition.artifact_name,
            "artifact_type": definition.artifact_type,
            "cache_layer": definition.cache_layer,
            "redis_key": artifact_key(definition.cache_layer, definition.artifact_name),
            "source_path": str(path),
            "required": definition.required,
            "exists_local": path.exists(),
            "stored_in_redis": False,
            "in_sync": False,
        }

        if path.exists():
            try:
                artifact = build_local_artifact(definition)
                item.update({
                    "sha256": artifact["sha256"],
                    "size_bytes": artifact["size_bytes"],
                    "record_count": artifact["record_count"],
                    "local_mtime": artifact["metadata"]["local_mtime"],
                    "local_readable": True,
                })
            except Exception as exc:
                item.update({
                    "local_readable": False,
                    "error": str(exc),
                })
        results.append(item)
    return results


def _stored_artifact_metadata(cache_client, definition: ArtifactDefinition) -> dict | None:
    stored = cache_client.get(artifact_key(definition.cache_layer, definition.artifact_name))
    if not isinstance(stored, dict):
        return None
    return {
        "artifact_name": stored.get("artifact_name"),
        "artifact_type": stored.get("artifact_type"),
        "cache_layer": stored.get("cache_layer"),
        "sha256": stored.get("sha256"),
        "size_bytes": stored.get("size_bytes"),
        "record_count": stored.get("record_count"),
        "status": stored.get("status"),
        "metadata": stored.get("metadata", {}),
    }


def check_redis_artifacts(cache_client) -> dict:
    """Compare local artifacts with artifact payloads currently stored in Redis."""
    local_items = inspect_local_artifacts()

    for item in local_items:
        definition = next(
            d for d in ALL_ARTIFACTS
            if d.artifact_name == item["artifact_name"]
            and d.cache_layer == item["cache_layer"]
        )
        stored = _stored_artifact_metadata(cache_client, definition)
        if not stored:
            continue
        item["stored_in_redis"] = True
        item["stored_sha256"] = stored.get("sha256")
        item["stored_metadata"] = stored.get("metadata", {})
        item["in_sync"] = item.get("sha256") == stored.get("sha256")

    missing_local = [i["artifact_name"] for i in local_items if i["required"] and not i["exists_local"]]
    missing_redis = [i["artifact_name"] for i in local_items if i["required"] and not i["stored_in_redis"]]
    stale_redis = [
        i["artifact_name"]
        for i in local_items
        if i["exists_local"] and i["stored_in_redis"] and not i["in_sync"]
    ]

    return {
        "ok": not missing_local and not missing_redis and not stale_redis,
        "backend": "upstash_redis",
        "missing_local": missing_local,
        "missing_redis": missing_redis,
        "stale_redis": stale_redis,
        "artifacts": local_items,
    }


def sync_redis_artifacts(cache_client) -> dict:
    """Store all readable local artifacts into Upstash Redis."""
    index = []
    synced = []
    skipped = []

    for definition in ALL_ARTIFACTS:
        path = _artifact_path(definition)
        if not path.exists():
            skipped.append({
                "artifact_name": definition.artifact_name,
                "reason": "missing_local_file",
                "source_path": str(path),
            })
            continue

        try:
            artifact = build_local_artifact(definition)
            key = artifact_key(definition.cache_layer, definition.artifact_name)
            if not cache_client.set(key, artifact):
                raise RuntimeError("redis_set_failed")
            index.append({
                "artifact_name": definition.artifact_name,
                "cache_layer": definition.cache_layer,
                "redis_key": key,
                "sha256": artifact["sha256"],
            })
            synced.append({
                "artifact_name": definition.artifact_name,
                "cache_layer": definition.cache_layer,
                "redis_key": key,
                "sha256": artifact["sha256"],
                "status": "cached",
            })
        except Exception as exc:
            skipped.append({
                "artifact_name": definition.artifact_name,
                "reason": str(exc),
                "source_path": str(path),
            })

    cache_client.set(REDIS_INDEX_KEY, index)
    status = check_redis_artifacts(cache_client)
    return {
        "synced_count": len(synced),
        "skipped_count": len(skipped),
        "synced": synced,
        "skipped": skipped,
        "status": status,
    }
