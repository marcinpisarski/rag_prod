"""Routes for knowledge base search and query"""
import json
import logging
import time
from typing import AsyncIterator, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services import AnswerResponse, LLMService
from app.services.query_service import (
    format_retrieval_results,
    log_query,
    run_search,
    search_stream_events,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/queries", tags=["queries"])


class QueryRequest(BaseModel):
    """Search query request"""
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    include_answer: bool = Field(default=True)
    use_rerank: Optional[bool] = Field(default=None, description="Override rerank_enabled setting")


class RetrievalResult(BaseModel):
    """Single retrieval result"""
    segment_id: int
    document_id: Optional[str] = None
    document_title: Optional[str] = None
    text: str
    page_number: Optional[int]
    similarity_score: float
    rerank_score: Optional[float] = None


class QueryResponse(BaseModel):
    """Query response with results and optional answer"""
    question: str
    retrieval_results: List[RetrievalResult]
    answer: Optional[AnswerResponse] = None
    execution_time_ms: float
    rerank_applied: bool = False


def _to_retrieval_models(results: List[dict]) -> List[RetrievalResult]:
    return [
        RetrievalResult(
            segment_id=item["segment_id"],
            document_id=item.get("document_id"),
            document_title=item.get("document_title"),
            text=item["text"],
            page_number=item.get("page_number"),
            similarity_score=item.get("similarity_score", 0.0),
            rerank_score=item.get("rerank_score"),
        )
        for item in format_retrieval_results(results)
    ]


@router.post("/search")
async def search(request: QueryRequest) -> QueryResponse:
    """
    Search the knowledge base for relevant content.

    Performs hybrid search, optional cross-encoder reranking, and LLM answer generation.
    """
    start_time = time.time()

    try:
        logger.info(
            f"Search query: '{request.question}' "
            f"(top_k={request.top_k}, include_answer={request.include_answer})"
        )

        search_results, _search_ms = run_search(
            request.question,
            top_k=request.top_k,
            use_rerank=request.use_rerank,
        )

        retrieval_results = _to_retrieval_models(search_results)

        answer = None
        if request.include_answer and search_results:
            llm_svc = LLMService()
            answer = llm_svc.generate_answer(request.question, search_results)
            logger.info(f"Generated answer with {len(answer.sources)} citations")

        execution_time = (time.time() - start_time) * 1000
        log_query(request.question, len(search_results), execution_time)

        rerank_applied = any(item.get("rerank_score") is not None for item in search_results)

        return QueryResponse(
            question=request.question,
            retrieval_results=retrieval_results,
            answer=answer,
            execution_time_ms=execution_time,
            rerank_applied=rerank_applied,
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Search error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _sse_generator(events: AsyncIterator[dict]) -> AsyncIterator[str]:
    async for item in events:
        yield _format_sse(item["event"], item["data"])


@router.post("/search/stream")
async def search_stream(request: QueryRequest):
    """
    Stream search progress, retrieval results, and answer tokens via Server-Sent Events.

    Event types: progress, retrieval, token, answer, done, error
    """
    events = search_stream_events(
        question=request.question,
        top_k=request.top_k,
        include_answer=request.include_answer,
        use_rerank=request.use_rerank,
    )
    return StreamingResponse(
        _sse_generator(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analytics")
async def get_analytics():
    """Get search analytics"""
    from sqlalchemy import func
    from app.services.query_service import SessionLocal
    from app.models import QueryLog

    db = SessionLocal()
    try:
        total_queries = db.query(QueryLog).count()
        avg_response_time = db.query(func.avg(QueryLog.response_time_ms)).scalar() or 0
        return {
            "total_queries": total_queries,
            "average_response_time_ms": float(avg_response_time),
            "status": "operational",
        }
    finally:
        db.close()
