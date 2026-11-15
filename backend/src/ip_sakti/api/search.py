"""HTTP boundary for the reusable retrieval service; no generation or UI coupling."""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import PyMongoError

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    jurisdiction: Literal["india", "international"] | None = None
    document_id: str | None = Field(default=None, min_length=1, max_length=128)
    kind: str | None = Field(default=None, min_length=1, max_length=64)
    language: Literal["hi", "en"] | None = None


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.7, ge=-1, le=1, allow_inf_nan=False)
    filters: SearchFilters | None = None
    include_unverified: bool = False


@router.post("/search")
def search(body: SearchRequest, request: Request):
    # Bound local CPU/memory usage and prevent concurrent lazy model loads.
    # The same service/embedder is reused for the application's lifetime.
    state = request.app.state
    if not state.retrieval_lock.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Retrieval is busy. Retry shortly.",
                            headers={"Retry-After": "1"})
    try:
        return state.retrieval.retrieve(
            body.query, top_k=body.top_k, min_score=body.min_score,
            filters=body.filters.model_dump(exclude_none=True) if body.filters else None,
            include_unverified=body.include_unverified)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except (PyMongoError, OSError, RuntimeError, ImportError) as error:
        log.warning("Retrieval unavailable (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Retrieval unavailable. Check database/index, corpus integrity and local model cache.") from None
    finally:
        state.retrieval_lock.release()
