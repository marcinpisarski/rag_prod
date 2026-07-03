# Quick Start Guide

## Installation & Setup

### 1. Create Virtual Environment
```bash
cd /home/marcin/Dokumenty/Cursor/rag_prod
python -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Database
```bash
python init_db.py
```

### 4. Configure Application (Optional)
```bash
cp .env.example .env
# Edit .env if needed (API keys, database settings, etc.)
```

### 4a. Setup Vector Database (Optional)

**For Development (In-Memory - Default)**
No extra setup needed. Vectors stored in application memory.

**For Qdrant (Recommended for Production)**
```bash
# Start Qdrant with Docker
docker run -p 6333:6333 qdrant/qdrant:latest
```

Then edit `.env`:
```env
VECTOR_DB_PROVIDER=qdrant
QDRANT_URL=http://localhost:6333
```

### 5. Start Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Access API
- **Interactive API Docs**: http://localhost:8000/api/docs
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

## Example Usage

### Upload a Document
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@example.pdf" \
  -F "title=Example PDF"
```

### Search Knowledge Base
```bash
curl -X POST "http://localhost:8000/api/queries/search" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What information is in the document?",
    "top_k": 5,
    "include_answer": true
  }'
```

### Check Document Status
```bash
curl "http://localhost:8000/api/documents/status?doc_id=<document_id>"
```

### View Analytics
```bash
curl "http://localhost:8000/api/queries/analytics"
```

## Architecture Overview

The application consists of:

1. **Configuration Layer** (`config.py`)
   - Environment-based settings
   - Type-safe configuration

2. **Data Layer** (`models/`)
   - SQLAlchemy ORM models
   - Database schema definitions

3. **Business Logic** (`services/`)
   - Document processing
   - Embedding generation
   - Hybrid search
   - Vector storage abstraction (Qdrant, in-memory)
   - LLM integration

4. **API Layer** (`routes/`)
   - Document management endpoints
   - Search endpoints
   - Query analytics

## Vector Database Support

| Provider | Use Case | Setup |
|----------|----------|-------|
| **In-Memory** | Development, testing | Default, no setup needed |
| **Qdrant** | Production, high-scale | `docker run -p 6333:6333 qdrant/qdrant:latest` |
| **Qdrant Cloud** | Managed, enterprise | Sign up at https://qdrant.io/ |

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application |
| `app/config.py` | Settings management |
| `app/models/database.py` | Database schema |
| `app/services/` | Business logic |
| `app/services/vector_store.py` | Vector storage (Qdrant/in-memory) |
| `app/routes/` | API endpoints |
| `requirements.txt` | Python dependencies |
| `.env.example` | Configuration template |
| `init_db.py` | Database setup |
| `README.md` | Full documentation |
| `ARCHITECTURE.md` | System architecture |
| `DEVELOPER.md` | Development guide |

## Configuration

Key environment variables:

- `DATABASE_URL`: Database connection (default: SQLite)
- `VECTOR_DB_PROVIDER`: Vector storage (memory, qdrant) (default: memory)
- `QDRANT_URL`: Qdrant server URL (e.g., http://localhost:6333)
- `LLM_API_KEY`: OpenAI API key for answer generation
- `EMBEDDING_PROVIDER`: local or cloud (default: local)
- `EMBEDDING_MODEL`: Model identifier (default: all-MiniLM-L6-v2)
- `DOCUMENT_CHUNK_SIZE`: Characters per segment (default: 2000)

## Supported Document Formats

- PDF (.pdf)
- Plain Text (.txt)
- Markdown (.md)

## Features

✅ **Hybrid Search** - Combines keyword (BM25) and semantic (embeddings) retrieval
✅ **Document Processing** - Automatic extraction, chunking, and indexing
✅ **Vector Storage** - Qdrant or in-memory storage options
✅ **LLM Integration** - Automatic answer generation with citations
✅ **Query Analytics** - Track and analyze search patterns
✅ **RESTful API** - Clean, well-documented endpoints
✅ **Production Ready** - Error handling, logging, and monitoring

## Troubleshooting

### Missing Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### Database Issues
```bash
# Reset database
rm kb_search.db
python init_db.py
```

### LLM Configuration
Ensure `LLM_API_KEY` is set in `.env`:
```bash
echo "LLM_API_KEY=your_key_here" >> .env
```

## Next Steps

1. Read [README.md](README.md) for complete feature overview
2. Check [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. Review [DEVELOPER.md](DEVELOPER.md) for development guidelines
