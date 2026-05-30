from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel

from ..insights.graph_insights import (
    get_graph_payload, get_suspects, get_alerts, get_timeline, get_summary
)
from ..insights.insight_schema import (
    GraphPayload, SuspectDetail, TransactionAlert, TimelineEvent, GraphSummary
)
from ..db.postgres_client import PostgresClient
from ..db.redis_client import RedisClient

app = FastAPI(title="TATVA Insights & Forensic API", version="1.1.0")

# Enable CORS for the frontend Vite server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Database and Cache clients
db = PostgresClient()
cache = RedisClient()

@app.on_event("startup")
def startup_event():
    """Ensure database tables exist on API startup."""
    if db.engine:
        try:
            db.create_tables()
            print("[API Startup] Supabase PostgreSQL tables verified/created.")
        except Exception as e:
            print(f"[API Startup] Failed to initialize PostgreSQL tables: {e}")
    else:
        print("[API Startup] WARNING: PostgreSQL client not connected.")

# ── REQUEST SCHEMAS ──────────────────────────────────────────

class CaseCreate(BaseModel):
    case_id: str
    title: str
    description: Optional[str] = ""
    investigator: Optional[str] = ""
    metadata: Optional[dict] = None

class NoteCreate(BaseModel):
    content: str
    author: Optional[str] = "analyst"
    entity_ref: Optional[str] = None
    tags: Optional[List[str]] = None

class EvidenceCreate(BaseModel):
    filename: str
    file_type: Optional[str] = "csv"
    file_hash: Optional[str] = ""
    record_count: Optional[int] = 0
    metadata: Optional[dict] = None

# ── ORIGINAL GRAPH & INSIGHTS ENDPOINTS ──────────────────────

@app.get("/api/graph", response_model=GraphPayload)
def read_graph(dataset: str = "UnifiedGraph"):
    """Returns the full unified graph. Caches in Redis and queries Neo4j."""
    # Log query to Postgres
    db.log_query(
        query_text=f"Fetched full graph for dataset '{dataset}'",
        query_type="graph_fetch",
        result_count=1,
        case_id=None
    )
    return get_graph_payload()

@app.get("/api/insights/suspects", response_model=List[SuspectDetail])
def read_suspects():
    """Returns a list of suspects scored by risk."""
    return get_suspects()

@app.get("/api/insights/transactions", response_model=List[TransactionAlert])
def read_transactions():
    """Returns flagged transactions (smurfing, circular flows, etc.)."""
    return get_alerts()

@app.get("/api/timeline", response_model=List[TimelineEvent])
def read_timeline():
    """Returns the temporal sequence of events across all sources."""
    return get_timeline()

@app.get("/api/insights/summary", response_model=GraphSummary)
def read_summary():
    """Returns global metrics of the graph."""
    return get_summary()

# ── NEW POSTGRES CASES & USER INPUTS ENDPOINTS ───────────────

@app.get("/api/cases")
def list_cases(status: Optional[str] = None):
    """List all investigation cases stored in Supabase."""
    try:
        return db.list_cases(status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cases")
def create_case(case: CaseCreate):
    """Create a new case in Supabase PostgreSQL."""
    try:
        return db.create_case(
            case_id=case.case_id,
            title=case.title,
            description=case.description,
            investigator=case.investigator,
            metadata=case.metadata
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    """Get details of a specific case, including metadata, notes, and evidence."""
    data = db.get_case(case_id=case_id)
    if not data:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Enrich with notes and evidence list
    data["notes"] = db.get_notes(case_id=case_id)
    data["evidence_files"] = db.get_evidence(case_id=case_id)
    return data

@app.post("/api/cases/{case_id}/notes")
def add_note(case_id: str, note: NoteCreate):
    """Add an investigator note or annotation to a case."""
    try:
        return db.add_note(
            case_id=case_id,
            content=note.content,
            author=note.author,
            entity_ref=note.entity_ref,
            tags=note.tags
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/cases/{case_id}/notes")
def get_notes(case_id: str):
    """Get all notes for a case."""
    return db.get_notes(case_id=case_id)

@app.post("/api/cases/{case_id}/evidence")
def add_evidence(case_id: str, ev: EvidenceCreate):
    """Log an evidence file uploaded for a case."""
    try:
        return db.add_evidence(
            case_id=case_id,
            filename=ev.filename,
            file_type=ev.file_type,
            file_hash=ev.file_hash,
            record_count=ev.record_count,
            metadata=ev.metadata
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/cases/{case_id}/evidence")
def get_evidence(case_id: str):
    """Get all logged evidence files for a case."""
    return db.get_evidence(case_id=case_id)

# ── AUDIT & SYSTEM STATUS ENDPOINTS ─────────────────────────

@app.get("/api/audit")
def get_audit(limit: int = Query(default=50, ge=1, le=200)):
    """Retrieve audit trail logs of investigator actions."""
    return db.get_audit_log(limit=limit)

@app.get("/api/cache/stats")
def get_cache_stats():
    """Retrieve statistics of Upstash Redis cache (hits/keys)."""
    return cache.get_stats() if cache.connected else {"connected": False}

@app.post("/api/cache/clear")
def clear_insights_cache():
    """Manually invalidate cached graph insights."""
    if cache.connected:
        count = cache.invalidate_insights()
        return {"status": "success", "invalidated_keys_count": count}
    return {"status": "error", "message": "Redis not connected"}

@app.post("/api/case/process")
def process_case(case_id: str = Body(..., embed=True)):
    """Simulates evidence ingestion pipeline and updates PostgreSQL."""
    # Log progress to Supabase
    db.log_query(
        query_text=f"Triggered processing pipeline for case '{case_id}'",
        query_type="pipeline_trigger",
        result_count=1,
        case_id=case_id
    )
    # Clear old insights cache since new processing is starting
    if cache.connected:
        cache.invalidate_insights()
        
    return {
        "status": "success",
        "message": f"Evidence ingested for case {case_id} and pipeline started.",
        "cache_invalidated": cache.connected
    }
