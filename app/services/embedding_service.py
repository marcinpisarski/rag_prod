"""Embedding service - vector generation and management"""
import logging
from typing import List, Union
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Handles embedding generation and management"""
    
    def __init__(self, provider: str = None, model_name: str = None):
        self.provider = provider or settings.embedding_provider
        self.model_name = model_name or settings.embedding_model
        self.model = None
        self._initialize_provider()
    
    def _initialize_provider(self):
        """Initialize the embedding provider"""
        if self.provider == "local":
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading local embedding model: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info("✓ Local embedding service ready")
            except ImportError:
                logger.warning("sentence-transformers not installed, using OpenAI for embeddings")
                self.provider = "cloud"
                if not settings.llm_api_key:
                    logger.warning("API key not set, embeddings will use fallback (random vectors)")
                    self.model = None
                else:
                    logger.info(f"Using cloud embedding provider: {self.model_name}")
        elif self.provider == "cloud":
            if not settings.llm_api_key:
                logger.warning("No API key for cloud embeddings, using fallback")
                self.model = None
            else:
                logger.info(f"Using cloud embedding provider: {self.model_name}")
        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as numpy array
        """
        if self.provider == "local" and self.model is not None:
            try:
                embedding = self.model.encode(text, convert_to_numpy=True)
                return embedding
            except Exception as e:
                logger.error(f"Error generating embedding: {e}")
                raise
        elif self.provider == "cloud" and self.model is None:
            return self._embed_cloud(text)
        else:
            # Fallback: generate deterministic embedding from text hash
            return self._embed_fallback(text)
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        if self.provider == "local" and self.model is not None:
            try:
                # Use batch processing for efficiency
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    batch_embeddings = self.model.encode(batch, convert_to_numpy=True)
                    embeddings.extend(batch_embeddings)
                logger.info(f"Generated {len(embeddings)} embeddings")
            except Exception as e:
                logger.error(f"Error in batch embedding: {e}")
                raise
        elif self.provider == "cloud":
            embeddings = [self._embed_cloud(text) for text in texts]
        else:
            # Fallback: generate deterministic embeddings
            embeddings = [self._embed_fallback(text) for text in texts]
        
        return embeddings
    
    def _embed_cloud(self, text: str) -> np.ndarray:
        """Cloud-based embedding (e.g., OpenAI)"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.llm_api_key)
            response = client.embeddings.create(
                input=text,
                model=self.model_name
            )
            embedding = np.array(response.data[0].embedding)
            return embedding
        except Exception as e:
            logger.warning(f"Cloud embedding error, falling back to hash-based: {e}")
            return self._embed_fallback(text)
    
    def _embed_fallback(self, text: str) -> np.ndarray:
        """Fallback embedding using deterministic hash-based approach"""
        import hashlib
        # Generate deterministic embedding from text hash
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert to float vector of embedding dimension
        np.random.seed(int.from_bytes(hash_bytes[:8], 'big') % (2**31))
        embedding = np.random.randn(settings.embedding_dimension).astype(np.float32)
        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding
    
    def get_dimension(self) -> int:
        """Get embedding dimension size"""
        return settings.embedding_dimension
