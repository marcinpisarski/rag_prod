"""RAGAS metrics: faithfulness, answer relevancy, context precision/recall."""
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _is_valid_evaluation(evaluation: Dict) -> bool:
    answer = (evaluation.get("answer") or "").strip()
    if not answer or answer.startswith("["):
        return False
    contexts = evaluation.get("retrieval_results") or []
    return bool(contexts)


def _build_ragas_rows(evaluations: List[Dict], questions_by_id: Dict[str, Dict]) -> Dict[str, List]:
    rows = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    for evaluation in evaluations:
        if not _is_valid_evaluation(evaluation):
            continue

        question = questions_by_id.get(evaluation.get("question_id"), {})
        if question.get("category") == "unanswerable":
            continue

        contexts = [
            segment.get("text", "")
            for segment in (evaluation.get("retrieval_results") or [])
            if segment.get("text")
        ]
        if not contexts:
            continue

        rows["question"].append(evaluation.get("question", ""))
        rows["answer"].append(evaluation.get("answer", ""))
        rows["contexts"].append(contexts)
        rows["ground_truth"].append(question.get("expected") or evaluation.get("expected", ""))

    return rows


def run_ragas_metrics(
    evaluations: List[Dict],
    questions_by_id: Dict[str, Dict],
    llm_model: Optional[str] = None,
) -> Dict:
    """
    Run RAGAS evaluation on completed API results.

    Requires: pip install ragas datasets
    Requires: OPENAI_API_KEY or LLM_API_KEY in environment
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError as exc:
        raise ImportError(
            "RAGAS is not installed. Run: pip install ragas datasets"
        ) from exc

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set LLM_API_KEY or OPENAI_API_KEY for RAGAS evaluation")

    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key

    rows = _build_ragas_rows(evaluations, questions_by_id)
    if not rows["question"]:
        return {
            "status": "skipped",
            "reason": "No valid evaluations with answers and retrieved contexts",
            "scores": {},
            "samples_used": 0,
        }

    dataset = Dataset.from_dict(rows)
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

    logger.info("Running RAGAS on %s samples", len(rows["question"]))
    result = evaluate(dataset, metrics=metrics)

    scores = {}
    for metric_name, value in result.items():
        try:
            scores[metric_name] = round(float(value), 4)
        except (TypeError, ValueError):
            scores[metric_name] = value

    return {
        "status": "ok",
        "llm_model": llm_model or os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "samples_used": len(rows["question"]),
        "scores": scores,
    }


def print_ragas_summary(ragas_report: Dict) -> None:
    print("\n" + "=" * 60)
    print("RAGAS METRICS")
    print("=" * 60)

    if ragas_report.get("status") != "ok":
        print(f"Status: {ragas_report.get('status')}")
        print(f"Reason: {ragas_report.get('reason', 'n/a')}")
        print("=" * 60 + "\n")
        return

    print(f"Samples used: {ragas_report['samples_used']}")
    print(f"LLM model:    {ragas_report.get('llm_model', 'n/a')}")
    print("-" * 60)
    for name, value in ragas_report.get("scores", {}).items():
        print(f"  {name}: {value}")
    print("=" * 60 + "\n")
