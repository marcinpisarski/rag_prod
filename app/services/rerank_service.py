"""Cross-encoder reranking for retrieved segments."""
import logging
from typing import List, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

_reranker = None
_reranker_model_name: Optional[str] = None


class RerankService:
    """Reranks candidate passages with a cross-encoder model."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.rerank_model
        self._model = None

    def _get_model(self):
        global _reranker, _reranker_model_name
        if _reranker is not None and _reranker_model_name == self.model_name:
            return _reranker
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {self.model_name}")
            _reranker = CrossEncoder(self.model_name)
            _reranker_model_name = self.model_name
            self._model = _reranker
            return _reranker
        except ImportError:
            logger.warning("sentence-transformers not installed; reranking disabled")
            return None
        except Exception as exc:
            logger.error(f"Failed to load reranker: {exc}")
            return None

    def rerank(
        self,
        query: str,
        candidates: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        if not candidates:
            return []

        if not settings.rerank_enabled:
            return candidates[:top_k]

        model = self._get_model()
        if model is None:
            return candidates[:top_k]

        pairs = [(query, item["text"]) for item in candidates]
        scores = model.predict(pairs)

        reranked = []
        for item, score in zip(candidates, scores):
            updated = dict(item)
            updated["rerank_score"] = float(score)
            updated["combined_score"] = float(score)
            reranked.append(updated)

        reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
        logger.info(f"Reranked {len(candidates)} candidates -> top {top_k}")
        return reranked[:top_k]
