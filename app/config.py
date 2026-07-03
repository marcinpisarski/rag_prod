"""Application configuration and environment settings"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    app_name: str = "Knowledge Base Search Engine"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./kb_search.db"
    )
    
    # Vector Database
    vector_db_provider: str = os.getenv("VECTOR_DB_PROVIDER", "memory")  # memory, qdrant, postgres
    qdrant_url: Optional[str] = os.getenv("QDRANT_URL")  # http://localhost:6333
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    qdrant_collection_name: str = "documents"
    
    # LLM Configuration
    llm_provider: str = "openai"  # openai or local
    llm_api_key: Optional[str] = os.getenv("LLM_API_KEY")
    llm_model: str = "gpt-4o-mini"
    
    # Embedding Configuration
    embedding_provider: str = "local"  # local or cloud
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # Processing Parameters
    document_chunk_size: int = 2000
    document_chunk_overlap: int = 300
    max_context_chunks: int = 10
    retrieval_similarity_threshold: float = 0.5
    
    # Hybrid Search Weights
    keyword_search_weight: float = 0.35
    semantic_search_weight: float = 0.65

    # Reranking (cross-encoder)
    rerank_enabled: bool = True
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidate_count: int = 20

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


settings = Settings()
