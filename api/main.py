"""
FastAPI async backend — Multi-Agent RAG Telecom Billing RCA.

Endpoints:
  POST /rca/run          → submit anomaly, start pipeline in background, return job_id
  GET  /rca/status/{id}  → poll job status (queued/running/complete/failed)
  GET  /rca/stream/{id}  → SSE stream of per-step progress events
  GET  /health           → liveness check

Security:
  - CORS restricted to CORS_ORIGINS env var (default: localhost only)
  - Optional API key auth via X-API-Key header (enabled when RCA_API_KEY is set)
  - Rate limiting: 10 requests/minute per IP on /rca/run
  - Input validation: account_id regex, anomaly_type enum, features size limit
"""
import asyncio
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Literal, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CORS_ORIGINS, RCA_API_KEY

# ── Rate Limiting ──────────────────────────────────────────────────────────────
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address)
    _has_limiter = True
except ImportError:
    _has_limiter = False

app = FastAPI(
    title="Telecom Billing RCA API",
    description="Multi-Agent GraphRAG RCA pipeline — async REST + SSE",
    version="0.2.0",
)

if _has_limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS — restricted to configured origins ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── API Key Auth (optional — disabled when RCA_API_KEY is empty) ───────────────
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(_api_key_header)):
    """Verify API key. Skips auth entirely when RCA_API_KEY env var is empty."""
    if not RCA_API_KEY:
        return  # Auth disabled (dev mode)
    if api_key != RCA_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── In-memory job store with TTL eviction ──────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}
_MAX_JOBS = 1000
_JOB_TTL_SECONDS = 3600  # evict completed jobs older than 1 hour

PIPELINE_STEPS = [
    "investigator",
    "reasoner",
    "critic",
    "reporter",
]


def _evict_old_jobs():
    """Remove completed/failed jobs older than TTL. Called before adding new jobs."""
    if len(_jobs) <= _MAX_JOBS:
        return
    now = time.time()
    to_delete = []
    for jid, job in _jobs.items():
        finished = job.get("finished_at")
        if finished and (now - finished) > _JOB_TTL_SECONDS:
            to_delete.append(jid)
    for jid in to_delete:
        del _jobs[jid]
    # If still over limit, remove oldest by started_at
    if len(_jobs) > _MAX_JOBS:
        sorted_jobs = sorted(_jobs.items(), key=lambda x: x[1].get("started_at") or 0)
        for jid, _ in sorted_jobs[: len(_jobs) - _MAX_JOBS // 2]:
            del _jobs[jid]


# ── Request / Response Models ──────────────────────────────────────────────────
_ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


class AnomalyRequest(BaseModel):
    account_id: str = Field(..., max_length=50, description="Customer account identifier")
    anomaly_type: Literal[
        "zero_billing", "duplicate_charge", "usage_spike", "cdr_failure", "sla_breach"
    ] = Field(..., description="Anomaly classification type")
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    monthly_charges: float = Field(default=0.0, ge=0.0, le=100000.0)
    total_charges: float = Field(default=0.0, ge=0.0, le=10000000.0)
    tenure: int = Field(default=0, ge=0, le=1000)
    features: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, v: str) -> str:
        if not _ACCOUNT_ID_PATTERN.match(v):
            raise ValueError("account_id must contain only alphanumeric, underscore, or hyphen characters")
        return v

    @field_validator("features")
    @classmethod
    def validate_features_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        serialized = json.dumps(v, default=str)
        if len(serialized) > 4096:
            raise ValueError("features payload too large (max 4KB)")
        return v


class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | running | complete | failed
    current_step: Optional[str] = None
    completed_steps: list = []
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    trace_id: Optional[str] = None


def _update_job(job_id: str, **kwargs):
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)


async def _run_pipeline(job_id: str, anomaly: dict):
    """Run the 4-agent pipeline in a background task, updating job state at each step."""
    _update_job(job_id, status="running", started_at=time.time(), completed_steps=[])
    try:
        # ── Cache lookup ────────────────────────────────────────────────────────
        try:
            from src.utils.cache import get_cached_rca, set_cached_rca
            cached = get_cached_rca(anomaly)
            if cached is not None:
                _update_job(
                    job_id,
                    status="complete",
                    current_step="reporter",
                    completed_steps=PIPELINE_STEPS,
                    result=cached,
                    finished_at=time.time(),
                )
                return
        except Exception:
            pass  # Cache unavailable — continue to pipeline

        from src.agents.graph import build_graph

        graph = build_graph()

        initial_state = {
            "anomaly_data": anomaly,
            "pipeline_status": "started",
            "retrieved_docs": [],
            "retrieval_query": "",
            "retrieval_count": 0,
            "hypothesis": "",
            "root_cause": "",
            "confidence_score": 0.0,
            "evidence": [],
            "critique": "",
            "critique_passed": False,
            "rca_report": "",
            "revision_count": 0,
            "retrieval_strategy": "",
            "routing_explanation": "",
        }

        # Stream step events by intercepting graph execution
        completed = []
        final_state = initial_state.copy()

        for step_output in graph.stream(initial_state):
            for node_name, node_state in step_output.items():
                if node_name in PIPELINE_STEPS:
                    completed.append(node_name)
                    _update_job(
                        job_id,
                        current_step=node_name,
                        completed_steps=list(completed),
                    )
                final_state.update(node_state)

        # Extract result
        result = {
            "rca_report":         final_state.get("rca_report", ""),
            "root_cause":         final_state.get("root_cause", ""),
            "hypothesis":         final_state.get("hypothesis", ""),
            "confidence_score":   final_state.get("confidence_score", 0.0),
            "retrieval_strategy": final_state.get("retrieval_strategy", ""),
            "routing_explanation": final_state.get("routing_explanation", ""),
            "retrieval_count":    final_state.get("retrieval_count", 0),
            "revision_count":     final_state.get("revision_count", 0),
            "anomaly_type":       anomaly.get("anomaly_type"),
            "account_id":         anomaly.get("account_id"),
            "trace_id":           final_state.get("trace_id"),
        }

        # ── Cache result for future identical requests ──────────────────────────
        try:
            from src.utils.cache import set_cached_rca
            set_cached_rca(anomaly, result)
        except Exception:
            pass

        _update_job(
            job_id,
            status="complete",
            current_step="reporter",
            completed_steps=PIPELINE_STEPS,
            result=result,
            finished_at=time.time(),
            trace_id=final_state.get("trace_id"),
        )

    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            error=str(exc),
            finished_at=time.time(),
        )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "jobs_in_memory": len(_jobs)}


@app.post("/rca/run", response_model=JobStatus, status_code=202)
async def run_rca(
    request: AnomalyRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    _auth: None = Depends(verify_api_key),
):
    """Submit an anomaly for RCA. Returns job_id immediately; poll /rca/status/{id}."""
    _evict_old_jobs()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "current_step": None,
        "completed_steps": [],
        "result": None,
        "error": None,
        "started_at": None,
        "finished_at": None,
        "trace_id": None,
    }
    anomaly_dict = request.model_dump()
    background_tasks.add_task(_run_pipeline, job_id, anomaly_dict)
    return JobStatus(**_jobs[job_id])


# Apply rate limit decorator if slowapi is available
if _has_limiter:
    run_rca = limiter.limit("10/minute")(run_rca)


@app.get("/rca/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str, _auth: None = Depends(verify_api_key)):
    """Poll pipeline status. Returns completed_steps list for UI step indicator."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatus(**_jobs[job_id])


async def _sse_generator(job_id: str) -> AsyncGenerator[str, None]:
    """Yield SSE events as each pipeline step completes."""
    last_step_count = 0
    poll_interval = 0.5  # seconds
    max_wait = 300        # 5-minute timeout

    waited = 0.0
    while waited < max_wait:
        if job_id not in _jobs:
            yield f"event: error\ndata: {json.dumps({'error': 'job not found'})}\n\n"
            return

        job = _jobs[job_id]
        completed = job.get("completed_steps", [])

        # Emit new step events
        for step in completed[last_step_count:]:
            event = {"step": step, "status": "complete", "job_status": job["status"]}
            yield f"event: step\ndata: {json.dumps(event)}\n\n"
        last_step_count = len(completed)

        if job["status"] in ("complete", "failed"):
            final_event = {
                "job_status": job["status"],
                "result": job.get("result"),
                "error": job.get("error"),
            }
            yield f"event: done\ndata: {json.dumps(final_event)}\n\n"
            return

        await asyncio.sleep(poll_interval)
        waited += poll_interval

    yield f"event: timeout\ndata: {json.dumps({'error': 'pipeline timed out'})}\n\n"


@app.get("/rca/stream/{job_id}")
async def stream_rca(job_id: str, _auth: None = Depends(verify_api_key)):
    """
    Server-Sent Events stream of per-step pipeline progress.
    Events: step (investigator/reasoner/critic/reporter complete), done, error, timeout.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
