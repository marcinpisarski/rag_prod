"""Vector database service - abstraction for multiple vector storage backends"""
import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Abstract interface for vector storage"""
    
    def add_vectors(self, segment_ids: List[int], embeddings: List[np.ndarray], 
                   metadata: List[Dict]) -> bool:
        """Add vectors to storage"""
        raise NotImplementedError
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        """Search for similar vectors. Returns [(segment_id, score), ...]"""
        raise NotImplementedError
    
    def delete_by_document(self, document_id: str) -> bool:
        """Delete all vectors for a document"""
        raise NotImplementedError
    
    def health_check(self) -> bool:
        """Check if vector store is operational"""
        raise NotImplementedError


class QdrantVectorStore(VectorStore):
    """Qdrant vector database backend"""
    
    def __init__(self, collection_name: str = "documents", url: Optional[str] = None, 
                 api_key: Optional[str] = None):
        """
        Initialize Qdrant vector store.
        
        Args:
            collection_name: Name of the Qdrant collection
            url: Qdrant server URL (e.g., http://localhost:6333)
            api_key: Optional API key for Qdrant Cloud
        """
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct
            self.QdrantClient = QdrantClient
            self.Distance = Distance
            self.VectorParams = VectorParams
            self.PointStruct = PointStruct
        except ImportError:
            logger.error("qdrant-client not installed. Install with: pip install qdrant-client")
            raise
        
        self.collection_name = collection_name
        self.embedding_dim = settings.embedding_dimension
        
        # Initialize client
        if url:
            logger.info(f"Connecting to Qdrant at {url}")
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            logger.info("Using in-memory Qdrant client")
            self.client = QdrantClient(":memory:")
        
        # Create collection if it doesn't exist
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' exists")
        except Exception:
            logger.info(f"Creating collection '{self.collection_name}'")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=self.VectorParams(
                    size=self.embedding_dim,
                    distance=self.Distance.COSINE
                )
            )
    
    def add_vectors(self, segment_ids: List[int], embeddings: List[np.ndarray], 
                   metadata: List[Dict]) -> bool:
        """Add vectors to Qdrant collection"""
        try:
            points = []
            for seg_id, emb, meta in zip(segment_ids, embeddings, metadata):
                # Convert numpy array to list
                if isinstance(emb, np.ndarray):
                    emb = emb.tolist()
                
                point = self.PointStruct(
                    id=seg_id,
                    vector=emb,
                    payload={
                        'document_id': meta.get('document_id'),
                        'page_number': meta.get('page_number'),
                        'segment_index': meta.get('segment_index'),
                        'text': meta.get('text', ''),
                        'metadata': meta.get('metadata', {})
                    }
                )
                points.append(point)
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Added {len(points)} vectors to Qdrant")
            return True
        except Exception as e:
            logger.error(f"Error adding vectors to Qdrant: {e}")
            return False
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        """Search for similar vectors in Qdrant"""
        try:
            # Convert to list if needed
            if isinstance(query_embedding, np.ndarray):
                query_embedding = query_embedding.tolist()
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                with_payload=True
            )
            
            # Return [(segment_id, similarity_score), ...]
            search_results = []
            for result in results:
                search_results.append((result.id, result.score))
            
            return search_results
        except Exception as e:
            logger.error(f"Error searching Qdrant: {e}")
            return []
    
    def delete_by_document(self, document_id: str) -> bool:
        """Delete all vectors for a document from Qdrant"""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            logger.info(f"Deleted vectors for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from Qdrant: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check Qdrant server health"""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False


class InMemoryVectorStore(VectorStore):
    """In-memory vector store for development/testing"""
    
    def __init__(self):
        """Initialize in-memory vector store"""
        self.vectors: Dict[int, np.ndarray] = {}
        self.metadata: Dict[int, Dict] = {}
        logger.info("Using in-memory vector store")
    
    def add_vectors(self, segment_ids: List[int], embeddings: List[np.ndarray], 
                   metadata: List[Dict]) -> bool:
        """Add vectors to memory"""
        try:
            for seg_id, emb, meta in zip(segment_ids, embeddings, metadata):
                if isinstance(emb, list):
                    emb = np.array(emb)
                self.vectors[seg_id] = emb
                self.metadata[seg_id] = meta
            
            logger.info(f"Added {len(segment_ids)} vectors to memory")
            return True
        except Exception as e:
            logger.error(f"Error adding vectors to memory: {e}")
            return False
    
    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        """Search in-memory vectors"""
        try:
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding)
            
            similarities = []
            for seg_id, vector in self.vectors.items():
                # Cosine similarity
                similarity = np.dot(query_embedding, vector) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(vector) + 1e-10
                )
                similarities.append((seg_id, float(similarity)))
            
            # Sort by similarity descending
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_k]
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []
    
    def delete_by_document(self, document_id: str) -> bool:
        """Delete vectors for a document from memory"""
        try:
            to_delete = [
                seg_id for seg_id, meta in self.metadata.items()
                if meta.get('document_id') == document_id
            ]
            
            for seg_id in to_delete:
                del self.vectors[seg_id]
                del self.metadata[seg_id]
            
            logger.info(f"Deleted {len(to_delete)} vectors for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from memory: {e}")
            return False
    
    def health_check(self) -> bool:
        """Memory store is always healthy"""
        return True


def get_vector_store() -> VectorStore:
    """Factory function to get configured vector store"""
    provider = settings.vector_db_provider.lower()
    
    if provider == "qdrant":
        return QdrantVectorStore(
            collection_name=settings.qdrant_collection_name,
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key
        )
    elif provider == "memory":
        return InMemoryVectorStore()
    else:
        logger.warning(f"Unknown vector DB provider: {provider}, using memory")
        return InMemoryVectorStore()
