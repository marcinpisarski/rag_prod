"""Retrieval metrics: Recall@k, MRR, and document-level recall."""
import re
from typing import Dict, List, Optional

DOCUMENT_TITLE_MAP = {
    "readme": "README",
    "license": "LICENSE",
}

STOPWORDS = {
    "that", "this", "with", "from", "when", "what", "which", "under", "into",
    "about", "there", "their", "them", "than", "then", "does", "have", "been",
    "were", "will", "your", "they", "information", "provided", "documents",
    "document", "system", "license", "public", "answer", "question",
}


def extract_keywords(expected: str, hints: Optional[List[str]] = None) -> List[str]:
    """Build keyword list from explicit hints or expected answer text."""
    if hints:
        return [h.strip() for h in hints if h.strip()]

    if not expected or "no information" in expected.lower():
        return []

    tokens = re.findall(r"[a-zA-Z0-9_./:-]+", expected)
    keywords = []
    for token in tokens:
        lower = token.lower()
        if len(lower) < 3 or lower in STOPWORDS:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:10]


def segment_document_match(segment: Dict, document: str) -> bool:
    title = (segment.get("document_title") or "").upper()
    needle = DOCUMENT_TITLE_MAP.get(document or "", "").upper()
    return bool(needle and needle in title)


def keyword_overlap(text: str, keywords: List[str]) -> float:
    if not keywords:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in text_lower)
    return hits / len(keywords)


def is_relevant_segment(segment: Dict, question: Dict, keywords: List[str]) -> bool:
    if not segment_document_match(segment, question.get("document", "")):
        return False

    text = segment.get("text", "")
    expected = question.get("expected", "")

    if expected and len(expected) < 60 and expected.lower() in text.lower():
        return True

    if keywords and keyword_overlap(text, keywords) >= 0.34:
        return True

    return False


def recall_at_k(retrieval_results: List[Dict], question: Dict, keywords: List[str], k: int) -> Optional[float]:
    if question.get("category") == "unanswerable":
        return None

    top = (retrieval_results or [])[:k]
    if not top:
        return 0.0
    return 1.0 if any(is_relevant_segment(seg, question, keywords) for seg in top) else 0.0


def document_recall_at_k(retrieval_results: List[Dict], question: Dict, k: int) -> Optional[float]:
    if question.get("category") == "unanswerable":
        return None

    top = (retrieval_results or [])[:k]
    if not top:
        return 0.0
    document = question.get("document", "")
    return 1.0 if any(segment_document_match(seg, document) for seg in top) else 0.0


def mean_reciprocal_rank(retrieval_results: List[Dict], question: Dict, keywords: List[str]) -> Optional[float]:
    if question.get("category") == "unanswerable":
        return None

    for rank, segment in enumerate(retrieval_results or [], 1):
        if is_relevant_segment(segment, question, keywords):
            return 1.0 / rank
    return 0.0


def compute_retrieval_metrics(
    evaluations: List[Dict],
    questions_by_id: Dict[str, Dict],
    k: int = 5,
) -> Dict:
    """Compute aggregate retrieval metrics from evaluation results."""
    per_question = []
    recall_scores = []
    doc_recall_scores = []
    mrr_scores = []

    for evaluation in evaluations:
        question_id = evaluation.get("question_id")
        question = questions_by_id.get(question_id, {})
        keywords = extract_keywords(
            question.get("expected", ""),
            question.get("retrieval_hints"),
        )
        retrieval_results = evaluation.get("retrieval_results") or []

        recall = recall_at_k(retrieval_results, question, keywords, k)
        doc_recall = document_recall_at_k(retrieval_results, question, k)
        mrr = mean_reciprocal_rank(retrieval_results, question, keywords)

        entry = {
            "question_id": question_id,
            "category": question.get("category"),
            "document": question.get("document"),
            "recall_at_k": recall,
            "document_recall_at_k": doc_recall,
            "mrr": mrr,
            "keywords": keywords,
            "retrieved_count": len(retrieval_results),
        }
        per_question.append(entry)

        if recall is not None:
            recall_scores.append(recall)
        if doc_recall is not None:
            doc_recall_scores.append(doc_recall)
        if mrr is not None:
            mrr_scores.append(mrr)

    def avg(values: List[float]) -> Optional[float]:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "k": k,
        "questions_evaluated": len(per_question),
        "answerable_questions": len(recall_scores),
        "recall_at_k": avg(recall_scores),
        "document_recall_at_k": avg(doc_recall_scores),
        "mrr": avg(mrr_scores),
        "per_question": per_question,
    }


def print_retrieval_summary(metrics: Dict) -> None:
    print("\n" + "=" * 60)
    print("RETRIEVAL METRICS")
    print("=" * 60)
    print(f"k:                      {metrics['k']}")
    print(f"Answerable questions:   {metrics['answerable_questions']}")
    print(f"Recall@{metrics['k']}:              {metrics['recall_at_k']}")
    print(f"Document Recall@{metrics['k']}:   {metrics['document_recall_at_k']}")
    print(f"MRR:                    {metrics['mrr']}")
    print("=" * 60)

    weak = sorted(
        [q for q in metrics["per_question"] if q.get("recall_at_k") == 0.0 and q.get("recall_at_k") is not None],
        key=lambda item: item["question_id"],
    )[:5]
    if weak:
        print("\nLowest recall (sample):")
        for item in weak:
            print(f"  - {item['question_id']} ({item['document']})")
    print()
