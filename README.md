# Knowledge Base Search Engine

A modern, production-grade semantic search system for enterprise knowledge bases and document repositories.

## 🎯 Overview

This platform provides intelligent document indexing and retrieval capabilities combining:
- **Hybrid Search** - Keyword-based (BM25) + semantic (embeddings) retrieval
- **Semantic Understanding** - Transformer-based embeddings for semantic similarity
- **LLM Integration** - Automatic answer generation with source citations
- **Scalable Architecture** - Support for PostgreSQL + pgvector for large-scale deployments

## 🚀 Key Features

### Search Capabilities
- **Hybrid Retrieval**: Combines BM25 keyword search with semantic embeddings
- **Multi-format Support**: Handles PDF, TXT, and Markdown documents
- **Configurable Weights**: Fine-tune the balance between keyword and semantic results
- **Batched Embeddings**: Efficient processing of large document collections

### Backend Infrastructure
- **FastAPI**: Modern async Python framework with automatic API documentation
- **SQLAlchemy ORM**: Database-agnostic data access layer
- **Vector Databases**: Support for Qdrant or PostgreSQL + pgvector
- **Background Processing**: Asynchronous document indexing

### Intelligence Layer
- **Source Attribution**: LLM-generated answers include document citations
- **Confidence Scoring**: Each answer includes confidence metrics
- **Query Analytics**: Track and analyze search patterns
- **Fallback Handling**: Graceful degradation when insufficient context available

## 📋 Requirements

- Python 3.9+
- PostgreSQL 14+ (optional, SQLite default)
- OpenAI API key (for LLM features)

## 🔧 Installation

### 1. Clone and Setup Environment

```bash
git clone <repository>
cd knowledge-base-search
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Application

```bash
cp .env.example .env
# Edit .env with your settings (API keys, database URL, etc.)
```

### 4. Initialize Database

```bash
python -m app.models.database
```

## 🚀 Running the Application

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

The API will be available at `http://localhost:8000`
- Interactive docs: `http://localhost:8000/api/docs`
- OpenAPI spec: `http://localhost:8000/api/openapi.json`

## 📚 API Endpoints

### Document Management

**Upload Document**
```
POST /api/documents/upload
```
Upload a document (PDF, TXT, MD) for indexing. Processing happens asynchronously.

**Get Document Status**
```
GET /api/documents/{document_id}/status
```
Check indexing status and segment count.

**List Documents**
```
GET /api/documents/
```
Retrieve all indexed documents.

### Search & Query

**Search Knowledge Base**
```
POST /api/queries/search
```
Perform hybrid search with optional LLM answer generation.

Example request:
```json
{
  "question": "What are the system requirements?",
  "top_k": 5,
  "include_answer": true
}
```

**Get Analytics**
```
GET /api/queries/analytics
```
Retrieve search metrics and performance data.

## 🏗️ Architecture

```
app/
├── main.py              # FastAPI application
├── config.py            # Configuration management
├── models/
│   └── database.py      # SQLAlchemy schemas
├── services/
│   ├── document_processor.py      # Extract & segment
│   ├── embedding_service.py       # Vector generation
│   ├── retrieval_service.py       # Hybrid search
│   └── llm_service.py             # Answer generation
└── routes/
    ├── documents.py     # Document management endpoints
    └── queries.py       # Search endpoints
```

## ⚙️ Configuration

Key environment variables:

- `DATABASE_URL`: Database connection string
- `VECTOR_DB_PROVIDER`: Vector storage backend (memory, qdrant) (default: memory)
- `QDRANT_URL`: Qdrant server URL (e.g., http://localhost:6333)
- `QDRANT_API_KEY`: API key for Qdrant Cloud (optional)
- `LLM_PROVIDER`: LLM service provider (openai)
- `LLM_API_KEY`: API key for LLM service
- `EMBEDDING_PROVIDER`: local or cloud
- `EMBEDDING_MODEL`: Model identifier (default: all-MiniLM-L6-v2)
- `DOCUMENT_CHUNK_SIZE`: Characters per segment (default: 2000)
- `DOCUMENT_CHUNK_OVERLAP`: Overlap between segments (default: 300)

## 🗄️ Vector Database Setup

### In-Memory Storage (Development)
Default option, no setup required. Data is stored in application memory.

```env
VECTOR_DB_PROVIDER=memory
```

### Qdrant (Production-Grade)
Fast, scalable vector database optimized for semantic search.

**Option 1: Local Qdrant with Docker**
```bash
docker run -p 6333:6333 qdrant/qdrant:latest
```

**Option 2: Qdrant Cloud**
1. Create account at https://qdrant.io/
2. Create a cluster
3. Set environment variables:

```env
VECTOR_DB_PROVIDER=qdrant
QDRANT_URL=https://your-cluster-url:6333
QDRANT_API_KEY=your_api_key_here
QDRANT_COLLECTION_NAME=documents
```

## 🔍 Search Optimization

### Weights Configuration

Adjust the balance between keyword and semantic search:

```python
KEYWORD_SEARCH_WEIGHT = 0.35    # BM25 contribution
SEMANTIC_SEARCH_WEIGHT = 0.65   # Embedding contribution
```

### Embedding Models

Popular models:
- `all-MiniLM-L6-v2`: Fast, 384-dim (default)
- `all-mpnet-base-v2`: Higher quality, 768-dim
- `paraphrase-multilingual-MiniLM-L12-v2`: Multilingual support

## 📊 Performance

- **Query Latency**: 200-500ms typical for hybrid search
- **Throughput**: 100+ concurrent requests with 4 workers
- **Storage**: ~300 bytes per embedding (384-dim vector)

## 🐳 Docker Deployment

```bash
docker build -t kb-search .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e LLM_API_KEY=... \
  kb-search
```

## 🔐 Security Considerations

- Use environment variables for sensitive credentials
- Implement API authentication (JWT, API keys)
- Enable HTTPS in production
- Validate and sanitize user inputs
- Rate limit API endpoints

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Support

For issues and questions, please create an issue in the repository.

```bash
git clone https://github.com/marcinpisarski/rag_prod.git
cd rag_prod
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

### Running the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Project Structure

```
rag_prod/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models/
│   ├── routes/
│   └── services/
├── tests/
├── requirements.txt
├── .gitignore
└── README.md
```

## License

MIT
