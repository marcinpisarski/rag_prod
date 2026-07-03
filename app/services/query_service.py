"""Shared query pipeline: load segments, hybrid search, rerank, answer."""
import logging
import time
from typing import AsyncIterator, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import ContentSegment, KnowledgeBase, QueryLog, SemanticEmbedding
from app.services import EmbeddingService, HybridRetriever, LLMService, RerankService

logger = logging.getLogger(__name__)

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def load_indexed_segments(db) -> Tuple[List[Dict], List[np.ndarray]]:
    segments_data = db.query(ContentSegment).all()
    if not segments_data:
        return [], []

    doc_titles = {doc.id: doc.title for doc in db.query(KnowledgeBase).all()}

    segments: List[Dict] = []
    embeddings_list: List[np.ndarray] = []

    for seg in segments_data:
        embedding_record = (
            db.query(SemanticEmbedding)
            .filter(SemanticEmbedding.segment_id == seg.id)
            .first()
        )
        if not embedding_record:
            continue

        segments.append({
            "id": seg.id,
            "document_id": seg.document_id,
            "document_title": doc_titles.get(seg.document_id, "Unknown"),
            "page_number": seg.page_number,
            "segment_index": seg.segment_index,
            "text_content": seg.text_content,
            "segment_metadata": seg.segment_metadata,
        })

        if isinstance(embedding_record.vector_data, list):
            embeddings_list.append(np.array(embedding_record.vector_data))
        else:
            embeddings_list.append(embedding_record.vector_data)

    return segments, embeddings_list


def run_search(
    question: str,
    top_k: int = 5,
    use_rerank: Optional[bool] = None,
) -> Tuple[List[Dict], float]:
    """Execute hybrid search with optional reranking. Returns (results, search_ms)."""
    start = time.time()
    db = SessionLocal()
    try:
        segments, embeddings_list = load_indexed_segments(db)
        if not segments:
            raise ValueError("No documents in knowledge base. Please upload documents first.")
        if not embeddings_list:
            raise ValueError("No embeddings found. Please ensure documents are processed.")

        embedding_svc = EmbeddingService()
        query_embedding = embedding_svc.embed_text(question)

        candidate_count = max(top_k, settings.rerank_candidate_count)
        retriever = HybridRetriever(segments)
        candidates = retriever.hybrid_search(
            query=question,
            query_embedding=query_embedding,
            segment_embeddings=embeddings_list,
            top_k=candidate_count,
        )

        rerank_enabled = settings.rerank_enabled if use_rerank is None else use_rerank
        if rerank_enabled and candidates:
            reranker = RerankService()
            results = reranker.rerank(question, candidates, top_k)
        else:
            results = candidates[:top_k]

        search_ms = (time.time() - start) * 1000
        return results, search_ms
    finally:
        db.close()


def log_query(question: str, result_count: int, response_time_ms: float) -> None:
    db = SessionLocal()
    try:
        db.add(QueryLog(
            query_text=question,
            retrieved_segment_count=result_count,
            response_time_ms=response_time_ms,
        ))
        db.commit()
    finally:
        db.close()


def format_retrieval_results(results: List[Dict], truncate: int = 500) -> List[Dict]:
    formatted = []
    for result in results:
        formatted.append({
            "segment_id": result.get("segment_id"),
            "document_id": result.get("document_id"),
            "document_title": result.get("document_title"),
            "text": result.get("text", "")[:truncate],
            "page_number": result.get("page_number"),
            "similarity_score": result.get("combined_score", 0.0),
            "rerank_score": result.get("rerank_score"),
        })
    return formatted


async def search_stream_events(
    question: str,
    top_k: int = 5,
    include_answer: bool = True,
    use_rerank: Optional[bool] = None,
) -> AsyncIterator[Dict]:
    """Yield progress/result events for SSE streaming."""
    import asyncio

    total_start = time.time()

    yield {
        "event": "progress",
        "data": {"stage": "loading", "message": "Loading indexed documents..."},
    }

    db = SessionLocal()
    try:
        segments, embeddings_list = await asyncio.to_thread(load_indexed_segments, db)
    finally:
        db.close()

    if not segments:
        yield {"event": "error", "data": {"message": "No documents in knowledge base."}}
        return
    if not embeddings_list:
        yield {"event": "error", "data": {"message": "No embeddings found."}}
        return

    yield {
        "event": "progress",
        "data": {
            "stage": "embedding",
            "message": f"Embedding query ({len(segments)} segments indexed)...",
        },
    }

    embedding_svc = EmbeddingService()
    query_embedding = await asyncio.to_thread(embedding_svc.embed_text, question)

    yield {
        "event": "progress",
        "data": {"stage": "retrieving", "message": "Running hybrid search (BM25 + semantic)..."},
    }

    candidate_count = max(top_k, settings.rerank_candidate_count)
    retriever = HybridRetriever(segments)
    candidates = await asyncio.to_thread(
        retriever.hybrid_search,
        question,
        query_embedding,
        embeddings_list,
        candidate_count,
    )

    rerank_enabled = settings.rerank_enabled if use_rerank is None else use_rerank
    if rerank_enabled and candidates:
        yield {
            "event": "progress",
            "data": {
                "stage": "reranking",
                "message": f"Reranking {len(candidates)} candidates with cross-encoder...",
            },
        }
        reranker = RerankService()
        results = await asyncio.to_thread(reranker.rerank, question, candidates, top_k)
    else:
        results = candidates[:top_k]

    yield {
        "event": "retrieval",
        "data": {"results": format_retrieval_results(results), "count": len(results)},
    }

    answer_content = ""
    answer_meta = None

    if include_answer and results:
        yield {
            "event": "progress",
            "data": {"stage": "generating", "message": "Generating answer..."},
        }
        llm_svc = LLMService()
        try:
            async for token in llm_svc.stream_answer_tokens(question, results):
                answer_content += token
                yield {"event": "token", "data": {"content": token}}
            answer_meta = llm_svc.build_answer_from_context(question, results, answer_content)
            yield {"event": "answer", "data": answer_meta.model_dump()}
        except Exception as exc:
            logger.error(f"Streaming generation failed: {exc}")
            yield {"event": "error", "data": {"message": f"Answer generation failed: {exc}"}}

    execution_time_ms = (time.time() - total_start) * 1000
    await asyncio.to_thread(log_query, question, len(results), execution_time_ms)

    yield {
        "event": "done",
        "data": {
            "question": question,
            "execution_time_ms": execution_time_ms,
            "retrieval_count": len(results),
        },
    }
