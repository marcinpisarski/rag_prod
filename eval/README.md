# RAG Evaluation System

Framework for manually assessing search quality and cited answers in Knowledge Base Search Engine v2.0.

## Structure

```
eval/
├── README.md                 # This file
├── questions.jsonl           # 30 questions about eval/sample/ content
├── scoring.py                # Manual scoring models and logic
├── run_evaluation.py         # Run queries via API
├── run_metrics.py            # Automated retrieval + RAGAS metrics
├── analyze_results.py        # Analyze manual scoring results
├── load_sample_docs.py       # Load documents from eval/sample/
├── metrics/
│   ├── retrieval.py          # Recall@k, MRR, document recall
│   └── ragas_eval.py         # RAGAS faithfulness, relevancy, etc.
├── reports/                  # Generated metrics JSON (do not commit)
├── evaluation_results.json   # API run results (generated, do not commit)
└── sample/                   # Test corpus
    ├── SETUP.md
    ├── README.md             # q01–q22
    └── LICENSE.md            # q23–q30
```

## Concept

The evaluation checks whether the system:

1. **Retrieves the right passages** (hybrid search: BM25 + embeddings)
2. **Generates answers grounded in documents** (no hallucinations)
3. **Provides accurate citations** (document, page, segment, excerpt)
4. **Refuses to answer** when information is not in the documents

### Question mix (30 total)

| Category | Count | Description |
|----------|-------|-------------|
| `answerable` | 25 | Answer is present in the document |
| `multi-hop` | 3 | Requires combining 2+ passages |
| `unanswerable` | 2 | No answer — anti-hallucination test |

Questions grouped by document:
- **readme** (q01–q22) — `eval/sample/README.md`
- **license** (q23–q30) — `eval/sample/LICENSE.md`

## Scoring system

Each question: **0–6 points** across 3 categories (0–2 each):

| Category | 0 | 1 | 2 |
|----------|---|---|---|
| **Correctness** | Incorrect / hallucination | Partially correct | Correct |
| **Citations** | Missing or irrelevant | Weak | Accurate, support the answer |
| **Completeness** | Missing key elements | Mostly complete | Complete |

**Maximum:** 30 × 6 = **180 points**

## Step-by-step procedure

### Step 0: Start the API

```bash
pip install -r requirements.txt
cp .env.example .env   # set LLM_API_KEY for full evaluation
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 1: Load test documents from `eval/sample/`

```bash
python eval/load_sample_docs.py
```

Details: [sample/SETUP.md](sample/SETUP.md)

### Step 2: Run evaluation

```bash
# Full RAG evaluation (search + LLM answer)
python eval/run_evaluation.py

# Evaluation + automated metrics in one step
python eval/run_evaluation.py --metrics

# Include RAGAS (requires LLM_API_KEY, pip install ragas datasets)
python eval/run_evaluation.py --metrics --ragas

# Retrieval only (no LLM_API_KEY required)
python eval/run_evaluation.py --retrieval-only --metrics

# More context
python eval/run_evaluation.py --top-k 10
```

### Step 2b: Automated metrics (retrieval + RAGAS)

```bash
# From existing evaluation_results.json
python eval/run_metrics.py

# Run eval first, then metrics
python eval/run_metrics.py --run-eval --ragas

# Compare two metric reports (e.g. before/after reranking)
python eval/run_metrics.py --compare eval/reports/metrics_a.json eval/reports/metrics_b.json
```

**Retrieval metrics** (no extra API calls):
| Metric | Description |
|--------|-------------|
| `Recall@k` | Correct document + keyword overlap in top-k |
| `Document Recall@k` | Correct source document (README/LICENSE) in top-k |
| `MRR` | Mean reciprocal rank of first relevant segment |

Relevance uses `document` field + keywords from `expected` (or optional `retrieval_hints` in `questions.jsonl`). Unanswerable questions are excluded from retrieval averages.

**RAGAS metrics** (LLM-as-judge, uses `LLM_API_KEY`):
| Metric | Description |
|--------|-------------|
| `faithfulness` | Answer grounded in retrieved context |
| `answer_relevancy` | Answer addresses the question |
| `context_precision` | Retrieved chunks are relevant |
| `context_recall` | Retrieved chunks cover the ground truth |

Reports saved to `eval/reports/metrics_<timestamp>.json`.

### Step 3: Manual scoring

Edit `eval/evaluation_results.json` — add `correctness`, `citation_quality`, `completeness` (0–2) and optionally `notes`.

### Step 4: Analysis

```bash
python eval/analyze_results.py
python eval/analyze_results.py --question q01
python eval/analyze_results.py --guide
```

## API v2.0 mapping

| Operation | Endpoint |
|-----------|----------|
| Upload | `POST /api/documents/upload` |
| Status | `GET /api/documents/{id}/status` |
| List | `GET /api/documents/` |
| Search | `POST /api/queries/search` |

## Question format (`questions.jsonl`)

```json
{
  "id": "q01",
  "question": "What external accounting platform does the Financial Consolidation System integrate with?",
  "expected": "QuickBooks Online (QBO)",
  "must_cite": true,
  "category": "answerable",
  "document": "readme",
  "retrieval_hints": ["QuickBooks", "QBO"]
}
```

`document` field values: `readme` | `license`

Optional `retrieval_hints` improves retrieval metric precision. If omitted, keywords are extracted from `expected`.

## Target metrics (MVP)

| Metric | Target |
|--------|--------|
| Recall@5 (automated) | > 0.75 |
| MRR (automated) | > 0.70 |
| RAGAS faithfulness | > 0.80 |
| Correctness (manual avg) | > 1.5 / 2 (75%) |
| Citations (average) | > 1.5 / 2 (75%) |
| Completeness (average) | > 1.5 / 2 (75%) |
| Overall | > 135 / 180 (75%) |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `404 No documents` | Run `python eval/load_sample_docs.py` (files in `eval/sample/`) |
| No LLM answer | Set `LLM_API_KEY` or use `--retrieval-only` |
| RAGAS import error | `pip install ragas datasets` |
| Poor results on LICENSE | Increase `--top-k`; LICENSE is long — consider smaller chunk size |

## Iteration loop

1. Reset the database
2. `python eval/load_sample_docs.py`
3. `python eval/run_evaluation.py --metrics --ragas`
4. Optionally score manually and run `python eval/analyze_results.py`
5. Compare runs: `python eval/run_metrics.py --compare ...`
6. Adjust parameters and repeat
