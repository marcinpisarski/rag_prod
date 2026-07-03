# Developer Guide

## Quick Start

### 1. Setup Environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Application
```bash
cp .env.example .env
# Edit .env with your API keys and preferences
```

### 3. Initialize Database
```bash
python init_db.py
```

### 4. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

Open browser to: `http://localhost:8000/api/docs`

### Optional: Setup Qdrant for Vector Storage

**Using Docker (Recommended for Development):**
```bash
docker run -p 6333:6333 qdrant/qdrant:latest
```

Then update `.env`:
```env
VECTOR_DB_PROVIDER=qdrant
QDRANT_URL=http://localhost:6333
```

**Using Qdrant Cloud (Production):**
1. Create account at https://qdrant.io/
2. Create cluster and get API key
3. Update `.env`:
```env
VECTOR_DB_PROVIDER=qdrant
QDRANT_URL=https://your-cluster-url:6333
QDRANT_API_KEY=your_api_key
```

## Project Organization

### Configuration
- `config.py`: Centralized settings using Pydantic BaseSettings
- `.env`: Runtime environment variables
- `.env.example`: Configuration template

### Database Layer
- `models/database.py`: SQLAlchemy ORM definitions
- `init_db.py`: Database initialization script

### Business Logic (Services)
- `services/document_processor.py`: File extraction and chunking
- `services/embedding_service.py`: Vector generation
- `services/retrieval_service.py`: Hybrid search implementation
- `services/llm_service.py`: Answer generation with LLM
- `services/vector_store.py`: Vector storage abstraction (Qdrant, in-memory)

### API Endpoints (Routes)
- `routes/documents.py`: Document CRUD and management
- `routes/queries.py`: Search and analytics

## Common Tasks

### Add a New Document Type

1. Update `DocumentProcessor.process_file()` in `services/document_processor.py`:
```python
elif file_type.lower() == 'docx':
    pages = self.extract_from_docx(file_path)
```

2. Implement extraction method:
```python
def extract_from_docx(self, file_path: str) -> List[Dict]:
    """Extract text from DOCX file"""
    # Implementation here
    pass
```

3. Update supported formats in `routes/documents.py` file validation

### Switch Vector Database

In `.env`:
```env
# For in-memory (development)
VECTOR_DB_PROVIDER=memory

# For Qdrant
VECTOR_DB_PROVIDER=qdrant
QDRANT_URL=http://localhost:6333
```

Or programmatically:
```python
from app.services import get_vector_store

# Automatically uses configured provider
vector_store = get_vector_store()
```

### Modify Search Weights

Edit `config.py`:
```python
KEYWORD_SEARCH_WEIGHT = 0.40  # Increase keyword search
SEMANTIC_SEARCH_WEIGHT = 0.60
```

### Switch Embedding Models
Edit `.env`:
```
EMBEDDING_MODEL=all-mpnet-base-v2
```

Note: Dimension may change - update `EMBEDDING_DIMENSION` accordingly.

### Use Different LLM Provider

Extend `LLMService` in `services/llm_service.py`:
```python
elif self.llm_provider == "anthropic":
    return self._generate_with_anthropic(question, context_segments)
```

## Testing

### Unit Testing

Create tests in `tests/` directory:
```bash
mkdir -p tests
```

Example test:
```python
# tests/test_document_processor.py
import pytest
from app.services import DocumentProcessor

def test_chunk_text():
    processor = DocumentProcessor(chunk_size=1000, chunk_overlap=100)
    text = "A" * 2500
    pages = [{"page_number": 1, "text_content": text}]
    segments = processor.segment_content(pages)
    assert len(segments) > 1
```

Run tests:
```bash
pytest tests/ -v
```

### Manual Testing with cURL

Upload document:
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@example.pdf" \
  -F "title=Example Document"
```

Search:
```bash
curl -X POST "http://localhost:8000/api/queries/search" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is this document about?",
    "top_k": 5,
    "include_answer": true
  }'
```

## Debugging

### Enable Debug Logging
In `main.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export LOG_LEVEL=DEBUG
```

### Database Inspection

```bash
# SQLite
sqlite3 kb_search.db ".tables"
sqlite3 kb_search.db "SELECT COUNT(*) FROM content_segments;"

# PostgreSQL
psql -d kb_search -c "\dt"
psql -d kb_search -c "SELECT COUNT(*) FROM content_segments;"
```

### Debugging Hybrid Search

Add debug output in `services/retrieval_service.py`:
```python
print(f"Keyword results: {keyword_results}")
print(f"Semantic results: {semantic_results}")
print(f"Combined scores: {combined_scores}")
```

## Performance Optimization

### 1. Batch Embedding Generation
```python
# Good - batch processing
embeddings = embedding_svc.embed_batch(texts, batch_size=64)

# Bad - single processing
embeddings = [embedding_svc.embed_text(t) for t in texts]
```

### 2. Database Indexing
```sql
-- Add indexes for faster queries
CREATE INDEX idx_segment_doc ON content_segments(document_id);
CREATE INDEX idx_embedding_segment ON semantic_embeddings(segment_id);
```

### 3. Connection Pooling
```python
from sqlalchemy.pool import QueuePool
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40
)
```

### 4. Caching
Implement caching for frequent queries:
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_cached_embedding(text: str):
    return embedding_svc.embed_text(text)
```

## Deployment Checklist

- [ ] Install production dependencies: `pip install -r requirements.txt`
- [ ] Set all environment variables in `.env`
- [ ] Initialize database: `python init_db.py`
- [ ] Test with small document: Upload PDF and verify processing
- [ ] Configure reverse proxy (nginx/Apache)
- [ ] Enable HTTPS/SSL
- [ ] Set up logging and monitoring
- [ ] Configure database backups
- [ ] Test LLM API connectivity
- [ ] Load test with concurrent requests
- [ ] Document any custom configurations

## Troubleshooting

### "Module not found" Error
```bash
pip install -r requirements.txt
# Or specific module:
pip install sentence-transformers
```

### Database Connection Failed
```bash
# Check connection string format
# SQLite: sqlite:///./kb_search.db
# PostgreSQL: postgresql://user:pass@localhost:5432/db

# Test connection
python -c "from sqlalchemy import create_engine; create_engine('YOUR_URL').connect()"
```

### LLM API Key Issues
```bash
# Verify API key
echo $LLM_API_KEY

# Test OpenAI connection
python -c "from openai import OpenAI; OpenAI(api_key='KEY').models.list()"
```

### Slow Embeddings
- Use faster model: `all-MiniLM-L6-v2` (default)
- Enable GPU: `device='cuda'` in SentenceTransformer
- Increase batch size for batch processing

### Memory Issues with Large Documents
- Reduce chunk size in config
- Process documents in smaller batches
- Use cloud embeddings instead of local

## Resources

- FastAPI docs: https://fastapi.tiangolo.com/
- SQLAlchemy: https://docs.sqlalchemy.org/
- Sentence Transformers: https://www.sbert.net/
- BM25: https://en.wikipedia.org/wiki/Okapi_BM25
- OpenAI API: https://platform.openai.com/docs/
