"""Data models and database schema definitions"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    Vector = None


Base = declarative_base()


class KnowledgeBase(Base):
    """Represents a document in the knowledge base"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    document_type = Column(String, nullable=False)  # pdf, txt, md, etc.
    file_path = Column(String, nullable=True)
    indexed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending, processing, ready, failed
    doc_metadata = Column(JSON, nullable=True)


class ContentPage(Base):
    """Represents a page extracted from a knowledge base document"""
    __tablename__ = "content_pages"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    extracted_at = Column(DateTime, default=datetime.utcnow)


class ContentSegment(Base):
    """Chunked content segment for semantic search"""
    __tablename__ = "content_segments"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(String, ForeignKey("knowledge_bases.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=True)
    segment_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    segment_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SemanticEmbedding(Base):
    """Vector embeddings for content segments"""
    __tablename__ = "semantic_embeddings"
    
    segment_id = Column(Integer, ForeignKey("content_segments.id"), primary_key=True)
    
    if HAS_PGVECTOR:
        # Using PostgreSQL pgvector extension (384 dims for sentence-transformers)
        vector_data = Column(Vector(384), nullable=False)
    else:
        # Fallback: store as JSON array for SQLite/other databases
        vector_data = Column(JSON, nullable=False)
    
    embedding_model = Column(String, default="all-MiniLM-L6-v2")
    embedded_at = Column(DateTime, default=datetime.utcnow)


class QueryLog(Base):
    """Log of user queries for analytics and monitoring"""
    __tablename__ = "query_logs"
    
    id = Column(Integer, primary_key=True)
    query_text = Column(Text, nullable=False)
    retrieved_segment_count = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    user_feedback = Column(String, nullable=True)  # positive, negative, neutral
    created_at = Column(DateTime, default=datetime.utcnow)
