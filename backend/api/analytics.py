"""
Analytics and adaptive learning API endpoints.

GET  /analytics/dashboard          Dashboard summary stats
GET  /analytics/mastery            Topic mastery scores
GET  /analytics/weak-topics        Topics needing attention
POST /analytics/revision/start     Start a revision session
POST /analytics/revision/complete  Complete a revision session
GET  /analytics/benchmark          Get benchmark results
POST /analytics/benchmark/run      Run a new benchmark
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.mastery_service import (
    get_dashboard_stats, get_all_mastery, get_weak_topics,
    start_revision_session, complete_revision_session,
)
from backend.services.benchmark_service import run_benchmark, get_benchmark_history
from backend.models.factory import get_model

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


# ──────────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return get_dashboard_stats(db)


# ──────────────────────────────────────────────────────────────
# Mastery
# ──────────────────────────────────────────────────────────────

@router.get("/mastery")
def mastery(db: Session = Depends(get_db)):
    return {"mastery": get_all_mastery(db)}


@router.get("/weak-topics")
def weak_topics(threshold: float = 60.0, limit: int = 5, db: Session = Depends(get_db)):
    return {"weak_topics": get_weak_topics(db, threshold=threshold / 100, limit=limit)}


# ──────────────────────────────────────────────────────────────
# Revision
# ──────────────────────────────────────────────────────────────

class RevisionStartRequest(BaseModel):
    topic: Optional[str] = None
    document_id: Optional[int] = None
    num_rounds: int = Field(default=5, ge=1, le=10)


class RevisionCompleteRequest(BaseModel):
    session_id: int
    topic: str
    correct_answers: int = Field(ge=0)
    total_questions: int = Field(ge=1)


@router.post("/revision/start")
def start_revision(req: RevisionStartRequest, db: Session = Depends(get_db)):
    try:
        result = start_revision_session(
            db=db,
            topic=req.topic,
            document_id=req.document_id,
            num_rounds=req.num_rounds,
        )
        return result
    except Exception as e:
        logger.error(f"Revision start failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start revision session: {e}")


@router.post("/revision/complete")
def complete_revision(req: RevisionCompleteRequest, db: Session = Depends(get_db)):
    try:
        result = complete_revision_session(
            db=db,
            session_id=req.session_id,
            topic=req.topic,
            correct_answers=req.correct_answers,
            total_questions=req.total_questions,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete revision: {e}")


# ──────────────────────────────────────────────────────────────
# Benchmark
# ──────────────────────────────────────────────────────────────

@router.get("/benchmark")
def benchmark_history(limit: int = 10, db: Session = Depends(get_db)):
    history = get_benchmark_history(db, limit=limit)
    model_info = get_model().get_info()
    return {
        "current_model": {
            "name": model_info.name,
            "provider": model_info.provider,
            "backend": model_info.backend,
            "device": model_info.device,
            "is_available": model_info.is_available,
            "supports_npu": model_info.supports_npu,
            "supports_gpu": model_info.supports_gpu,
        },
        "history": history,
    }


@router.post("/benchmark/run")
def run_benchmark_endpoint(
    iterations: int = 3,
    db: Session = Depends(get_db),
):
    if iterations < 1 or iterations > 10:
        raise HTTPException(status_code=400, detail="iterations must be between 1 and 10")
    try:
        result = run_benchmark(db=db, iterations=iterations)
        return result
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e}")


# ──────────────────────────────────────────────────────────────
# Model info / settings
# ──────────────────────────────────────────────────────────────

@router.get("/model-info")
def model_info():
    from backend.services.benchmark_service import get_device_info
    m = get_model()
    info = m.get_info()
    return {
        "model": info.name,
        "provider": info.provider,
        "backend": info.backend,
        "device": info.device,
        "is_available": info.is_available,
        "supports_gpu": info.supports_gpu,
        "supports_npu": info.supports_npu,
        "context_length": info.context_length,
        "embedding_dims": info.embedding_dims,
        "metadata": info.metadata,
        "device_info": get_device_info(),
    }
