# Setup Sample Documents

Evaluation uses files from **`eval/sample/`** — not `eval/sample_docs/`.

## Sample corpus

| File | Content | Questions |
|------|---------|-----------|
| `README.md` | Financial Consolidation System — architecture, API, config, QBO integration | q01–q22 |
| `LICENSE.md` | Creative Commons BY-SA 4.0 International license text | q23–q30 |

## Prerequisites

```bash
pip install -r requirements.txt
cp .env.example .env          # set LLM_API_KEY for full RAG evaluation
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use a **fresh database** before loading samples to avoid duplicate segments from earlier runs.

## Option A: Automated loader (recommended)

```bash
python eval/load_sample_docs.py
```

Uploads every `.md` and `.txt` file in `eval/sample/` (except `SETUP.md`) via `POST /api/documents/upload`.

## Option B: Via curl

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@eval/sample/README.md" \
  -F "title=README"

curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@eval/sample/LICENSE.md" \
  -F "title=LICENSE"
```

Wait until each document reports `status: ready`:

```bash
curl http://localhost:8000/api/documents/
curl http://localhost:8000/api/documents/{document_id}/status
```

## Verification

Each document should have:
- `status`: `ready`
- `segment_count` > 0

Typical segment counts (chunk_size=2000, overlap=300):
- `README.md`: ~8–15 segments
- `LICENSE.md`: ~15–25 segments

## Test a single query

```bash
curl -X POST http://localhost:8000/api/queries/search \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What platform does the Financial Consolidation System integrate with?",
    "top_k": 5,
    "include_answer": true
  }'
```

Expected: retrieval hits `README.md`; answer mentions **QuickBooks Online (QBO)**.

## Run full evaluation

```bash
python eval/run_evaluation.py
python eval/analyze_results.py
```

See [eval/README.md](../README.md) for scoring procedure.

## Adding documents

1. Add `.md` or `.txt` to `eval/sample/`
2. Add questions to `eval/questions.jsonl`
3. Re-run `python eval/load_sample_docs.py` and `python eval/run_evaluation.py`

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No files found | Ensure files are in `eval/sample/`, not `eval/sample_docs/` |
| `.md` upload rejected | API supports `md` — check file extension |
| Stuck in `processing` | Check embedding model download; increase `--timeout 300` |
| Wrong answers | Reset DB, reload samples, try `--top-k 10` |
