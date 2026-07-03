"""Retrieval service - hybrid search (keyword + semantic)"""
import logging
from typing import List, Dict, Tuple, Optional
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False
    logger.warning("rank_bm25 not installed. Keyword search disabled.")


class HybridRetriever:
    """Performs hybrid retrieval combining keyword and semantic search"""
    
    def __init__(self, segments: List[Dict], keyword_weight: float = None, semantic_weight: float = None):
        """
        Initialize retriever with content segments.
        
        Args:
            segments: List of segment dictionaries with text_content
            keyword_weight: Weight for keyword-based search (default 0.35)
            semantic_weight: Weight for semantic search (default 0.65)
        """
        self.segments = segments
        self.keyword_weight = keyword_weight or settings.keyword_search_weight
        self.semantic_weight = semantic_weight or settings.semantic_search_weight
        
        # Initialize BM25 for keyword search
        if HAS_BM25:
            texts = [seg['text_content'] for seg in segments]
            tokenized = [self._tokenize(text) for text in texts]
            self.bm25 = BM25Okapi(tokenized)
            logger.info(f"BM25 index initialized with {len(segments)} segments")
        else:
            self.bm25 = None
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Simple tokenization for BM25.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        tokens = text.lower().split()
        tokens = [t.strip('.,!?;:()[]{}"\'-') for t in tokens]
        return [t for t in tokens if t]
    
    def keyword_search(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Perform keyword-based search using BM25.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (segment_index, score) tuples
        """
        if not self.bm25:
            logger.warning("BM25 not available, returning empty results")
            return []
        
        try:
            query_tokens = self._tokenize(query)
            scores = self.bm25.get_scores(query_tokens)
            
            # Get top-k indices
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0]
            
            return results
        except Exception as e:
            logger.error(f"Keyword search error: {e}")
            return []
    
    def semantic_search(self, query_embedding: np.ndarray, segment_embeddings: List[np.ndarray], 
                       top_k: int = 5, threshold: float = None) -> List[Tuple[int, float]]:
        """
        Perform semantic search using embeddings.
        
        Args:
            query_embedding: Embedding vector of the query
            segment_embeddings: List of embedding vectors for all segments
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            
        Returns:
            List of (segment_index, score) tuples
        """
        threshold = threshold or settings.retrieval_similarity_threshold
        
        try:
            # Calculate cosine similarity
            similarities = []
            for seg_emb in segment_embeddings:
                # Convert to numpy if needed
                if isinstance(seg_emb, list):
                    seg_emb = np.array(seg_emb)
                
                similarity = np.dot(query_embedding, seg_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(seg_emb) + 1e-10
                )
                similarities.append(similarity)
            
            similarities = np.array(similarities)
            
            # Get top-k results above threshold
            top_indices = np.argsort(similarities)[::-1]
            results = []
            for idx in top_indices[:top_k]:
                if similarities[idx] >= threshold:
                    results.append((int(idx), float(similarities[idx])))
            
            return results
        except Exception as e:
            logger.error(f"Semantic search error: {e}")
            return []
    
    def hybrid_search(self, query: str, query_embedding: np.ndarray, 
                     segment_embeddings: List[np.ndarray], top_k: int = 5) -> List[Dict]:
        """
        Perform hybrid search combining keyword and semantic results.
        
        Args:
            query: Search query string
            query_embedding: Embedding vector of the query
            segment_embeddings: List of embedding vectors for all segments
            top_k: Number of results to return
            
        Returns:
            List of result dictionaries sorted by combined score
        """
        # Get results from both search methods
        keyword_results = self.keyword_search(query, top_k * 2)  # Get more for combination
        semantic_results = self.semantic_search(query_embedding, segment_embeddings, top_k * 2)
        
        # Combine results
        combined_scores = {}
        
        # Normalize and combine keyword scores
        if keyword_results:
            max_score = max([score for _, score in keyword_results])
            for idx, score in keyword_results:
                normalized = score / max_score if max_score > 0 else 0
                combined_scores[idx] = combined_scores.get(idx, 0) + (normalized * self.keyword_weight)
        
        # Normalize and combine semantic scores
        if semantic_results:
            max_score = max([score for _, score in semantic_results])
            for idx, score in semantic_results:
                normalized = score / max_score if max_score > 0 else 0
                combined_scores[idx] = combined_scores.get(idx, 0) + (normalized * self.semantic_weight)
        
        # Sort by combined score
        sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        # Build result dictionaries
        results = []
        for segment_idx, combined_score in sorted_results:
            segment = self.segments[segment_idx]
            results.append({
                'segment_id': segment['id'],
                'document_id': segment.get('document_id'),
                'document_title': segment.get('document_title', 'Unknown'),
                'text': segment['text_content'],
                'page_number': segment.get('page_number'),
                'segment_index': segment.get('segment_index'),
                'combined_score': combined_score,
                'metadata': segment.get('segment_metadata'),
            })
        
        logger.info(f"Hybrid search returned {len(results)} results")
        return results
