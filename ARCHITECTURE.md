# Project Structure Overview

## Complete Application Architecture

```
rag_prod/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app factory & startup
│   ├── config.py                        # Settings & environment config
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py                  # SQLAlchemy ORM models
│   │       ├── KnowledgeBase            # Document metadata
│   │       ├── ContentPage              # Extracted pages
│   │       ├── ContentSegment           # Chunked segments
│   │       ├── SemanticEmbedding        # Vector data
│   │       └── QueryLog                 # Analytics
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_processor.py        # PDF/TXT extraction, chunking
│   │   ├── embedding_service.py         # Local/cloud embeddings
│   │   ├── retrieval_service.py         # BM25 + semantic hybrid search
│   │   ├── llm_service.py               # LLM answer generation
│   │   └── vector_store.py              # Vector storage abstraction (Qdrant, in-memory)
│   │
│   └── routes/
│       ├── __init__.py
│       ├── documents.py                 # POST/GET document endpoints
│       └── queries.py                   # Search endpoint
│
├── init_db.py                           # Database initialization
├── requirements.txt                     # Python dependencies
├── .env.example                         # Configuration template
└── README.md                            # Documentation

```

## Module Descriptions

### Configuration (`config.py`)
- Pydantic BaseSettings for environment-based configuration
- Settings for database, LLM, embeddings, and processing
- Support for .env file loading

### Models (`models/database.py`)
- **KnowledgeBase**: Stores document metadata (title, type, status)
- **ContentPage**: Raw extracted pages from documents
- **ContentSegment**: Chunked content for semantic search
- **SemanticEmbedding**: Vector representations (pgvector support)
- **QueryLog**: Query history for analytics

### Services Layer

#### DocumentProcessor
- PDF extraction using PyPDF2
- Text file support
- Configurable chunking with overlap
- Full processing pipeline

#### EmbeddingService
- Local embeddings (sentence-transformers)
- Cloud embeddings (OpenAI)
- Batch processing support
- Configurable models

#### HybridRetriever
- BM25 keyword search
- Semantic similarity search
- Hybrid score combination
- Configurable weights (35% keyword, 65% semantic)

#### LLMService
- OpenAI integration
- Structured JSON responses
- Citation extraction
- Confidence scoring

#### VectorStore
- Abstract interface for vector storage backends
- **QdrantVectorStore**: Production-grade Qdrant integration
  - Support for local Qdrant servers
  - Support for Qdrant Cloud
  - Efficient vector similarity search
  - Collection-based organization
- **InMemoryVectorStore**: Development/testing option
  - No external dependencies
  - Fast in-memory operations
  - Automatic similarity computation

### Routes Layer

#### Documents Router (`/api/documents`)
- POST `/upload` - Upload and queue document for processing
- GET `/{doc_id}/status` - Check indexing progress
- GET `/` - List all documents

#### Queries Router (`/api/queries`)
- POST `/search` - Hybrid search with optional LLM answer
- GET `/analytics` - Query performance metrics

## Key Implementation Details

### Hybrid Search Formula
```
combined_score = (keyword_score_normalized × 0.35) + (semantic_score_normalized × 0.65)
```

### Processing Pipeline
1. Document upload → Store file
2. Extract pages → PDF/TXT parsing
3. Create segments → Chunking with overlap
4. Generate embeddings → Batch process with sentence-transformers
5. Store in database → Ready for search

### Search Pipeline
1. Query embedding → Generate vector representation
2. Keyword search → BM25 on text content
3. Semantic search → Cosine similarity on vectors
4. Combine results → Weighted score aggregation
5. Generate answer → LLM with retrieved context (optional)

## Configuration Parameters

- `DOCUMENT_CHUNK_SIZE`: 2000 chars per segment
- `DOCUMENT_CHUNK_OVERLAP`: 300 chars overlap
- `KEYWORD_SEARCH_WEIGHT`: 0.35
- `SEMANTIC_SEARCH_WEIGHT`: 0.65
- `MAX_CONTEXT_CHUNKS`: 10 segments for LLM
- `EMBEDDING_DIMENSION`: 384 (all-MiniLM-L6-v2)

## Database Schema

### SQL Database Schema (SQLite/PostgreSQL)
- KnowledgeBase → ContentPage (1:N)
- KnowledgeBase → ContentSegment (1:N)
- ContentSegment → SemanticEmbedding (1:1)

### Vector Storage Options

#### Qdrant Backend
- **Architecture**: Separate vector database (cloud or self-hosted)
- **Collection**: Documents collection with vectors and payloads
- **Vector Space**: COSINE distance metric
- **Payload Storage**: Document ID, page number, segment index, text preview
- **Advantages**: 
  - Production-grade performance
  - Distributed architecture support
  - Advanced filtering capabilities
  - Managed cloud option

#### In-Memory Backend
- **Architecture**: Vectors stored in application memory
- **Use Cases**: Development, testing, small deployments
- **Advantages**:
  - No external dependencies
  - Instant startup
  - Fast for small datasets
- **Limitations**: Data lost on restart, not suitable for production

## Database Schema (Legacy)

### SQL Tables (for metadata, not vectors)
- KnowledgeBase → ContentPage (1:N)
- KnowledgeBase → ContentSegment (1:N)
- ContentSegment → SemanticEmbedding (1:1)
## API Response Examples

### Search Response
```json
{
  "question": "What are system requirements?",
  "retrieval_results": [
    {
      "segment_id": 42,
      "text": "System requires Python 3.9+...",
      "page_number": 5,
      "similarity_score": 0.87
    }
  ],
  "answer": {
    "content": "The system requires Python 3.9+ and...",
    "sources": [
      {
        "document_id": "uuid",
        "document_title": "README.md",
        "page_number": 5,
        "segment_id": 42,
        "excerpt": "System requires Python 3.9+"
      }
    ],
    "has_relevant_content": true,
    "confidence": 0.92
  },
  "execution_time_ms": 245.3
}
```

## Performance Characteristics

- Document indexing: ~50-200ms per page (depends on embedding model)
- Query latency: 200-500ms (hybrid search + LLM optional)
- Throughput: 100+ concurrent requests (4 workers)
- Storage: ~300 bytes per 384-dim embedding

## Deployment Options

### Development
```bash
uvicorn app.main:app --reload
```

### Production
```bash
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Docker
```bash
docker build -t kb-search .
docker run -p 8000:8000 kb-search
```

### PostgreSQL Setup
```sql
CREATE DATABASE kb_search;
CREATE EXTENSION vector;
```

## Dependencies Overview

- **fastapi**: Web framework
- **sqlalchemy**: ORM
- **pydantic**: Data validation
- **sentence-transformers**: Embeddings
- **rank-bm25**: Keyword search
- **PyPDF2**: PDF processing
- **openai**: LLM API
- **uvicorn**: ASGI server
