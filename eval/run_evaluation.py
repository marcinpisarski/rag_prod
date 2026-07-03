#!/usr/bin/env python3
"""Run evaluation: query all questions and save results for manual scoring."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import requests

from eval.scoring import (
    EvaluationResults,
    QuestionEvaluation,
    load_questions,
    print_scoring_guide,
    save_evaluation,
)


def normalize_citations(sources: list) -> list:
    citations = []
    for source in sources or []:
        citations.append({
            "document_id": source.get("document_id"),
            "document_title": source.get("document_title"),
            "page_number": source.get("page_number"),
            "segment_id": source.get("segment_id"),
            "chunk_id": source.get("segment_id"),
            "quote": source.get("excerpt") or source.get("quote", ""),
        })
    return citations


def parse_search_response(data: dict, include_answer: bool) -> tuple[str, list, bool, list]:
    answer_data = data.get("answer")
    retrieval_results = data.get("retrieval_results", [])

    if answer_data:
        return (
            answer_data.get("content", ""),
            normalize_citations(answer_data.get("sources", [])),
            answer_data.get("has_relevant_content", False),
            retrieval_results,
        )

    if include_answer:
        top_segments = [
            f"[seg {r.get('segment_id')}] {r.get('text', '')[:200]}"
            for r in retrieval_results[:3]
        ]
        preview = "\n".join(top_segments) if top_segments else "No retrieval results"
        return (
            f"[NO LLM ANSWER] Top retrieval:\n{preview}",
            [],
            bool(retrieval_results),
            retrieval_results,
        )

    preview = "\n".join(
        f"[seg {r.get('segment_id')}, score={r.get('similarity_score', 0):.3f}] {r.get('text', '')[:160]}"
        for r in retrieval_results[:5]
    )
    return preview or "[NO RESULTS]", [], bool(retrieval_results), retrieval_results


def run_evaluation(
    api_url: str = "http://localhost:8000",
    top_k: int = 5,
    include_answer: bool = True,
    questions_file: str = "eval/questions.jsonl",
    output_file: str = "eval/evaluation_results.json",
):
    print(f"\nStarting evaluation against {api_url}")
    print(f"  top_k={top_k}, include_answer={include_answer}")

    try:
        health = requests.get(f"{api_url}/health", timeout=10)
        health.raise_for_status()
    except Exception as exc:
        print(f"API health check failed: {exc}")
        print("Start the API first: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return None

    questions = load_questions(questions_file)
    print(f"Loaded {len(questions)} questions from {questions_file}")

    evaluations = []
    for index, question in enumerate(questions, 1):
        print(f"\n[{index}/{len(questions)}] {question['id']}: {question['question'][:60]}...")

        try:
            response = requests.post(
                f"{api_url}/api/queries/search",
                json={
                    "question": question["question"],
                    "top_k": top_k,
                    "include_answer": include_answer,
                },
                timeout=120,
            )

            if response.status_code == 200:
                data = response.json()
                answer, citations, has_context, retrieval_results = parse_search_response(
                    data, include_answer
                )
                print(
                    f"  OK answer={len(answer)} chars, citations={len(citations)}, "
                    f"retrieved={len(retrieval_results)}"
                )
                evaluations.append(
                    QuestionEvaluation(
                        question_id=question["id"],
                        question=question["question"],
                        expected=question["expected"],
                        answer=answer,
                        citations=citations,
                        has_sufficient_context=has_context,
                        category=question.get("category"),
                        document=question.get("document"),
                        retrieval_results=retrieval_results,
                    )
                )
            else:
                print(f"  API error {response.status_code}: {response.text[:120]}")
                evaluations.append(
                    QuestionEvaluation(
                        question_id=question["id"],
                        question=question["question"],
                        expected=question["expected"],
                        answer=f"[ERROR {response.status_code}]: {response.text[:200]}",
                        citations=[],
                        has_sufficient_context=False,
                        category=question.get("category"),
                        document=question.get("document"),
                    )
                )
        except Exception as exc:
            print(f"  Exception: {exc}")
            evaluations.append(
                QuestionEvaluation(
                    question_id=question["id"],
                    question=question["question"],
                    expected=question["expected"],
                    answer=f"[EXCEPTION]: {exc}",
                    citations=[],
                    has_sufficient_context=False,
                    category=question.get("category"),
                    document=question.get("document"),
                )
            )

    results = EvaluationResults(
        evaluations=evaluations,
        api_url=api_url,
        top_k=top_k,
        include_answer=include_answer,
    )
    save_evaluation(results, output_file)

    print(f"\nEvaluation complete. Results saved to: {output_file}")
    print(f"  Successful queries: {sum(1 for e in evaluations if not e.answer.startswith('['))}")
    print(f"  With context: {sum(1 for e in evaluations if e.has_sufficient_context)}")
    print(f"  With citations: {sum(1 for e in evaluations if e.citations)}")
    print("\nNext step: manually score results in evaluation_results.json")
    print_scoring_guide()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAG evaluation against Knowledge Base Search API")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Skip LLM answer generation (no LLM_API_KEY required)",
    )
    parser.add_argument("--questions", default="eval/questions.jsonl")
    parser.add_argument("--output", default="eval/evaluation_results.json")
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Run retrieval metrics (and RAGAS with --ragas) after evaluation",
    )
    parser.add_argument("--ragas", action="store_true", help="Include RAGAS when using --metrics")
    args = parser.parse_args()

    results = run_evaluation(
        api_url=args.api_url,
        top_k=args.top_k,
        include_answer=not args.retrieval_only,
        questions_file=args.questions,
        output_file=args.output,
    )

    if args.metrics and results:
        from eval.run_metrics import run_metrics

        run_metrics(
            input_file=args.output,
            k=args.top_k,
            run_ragas=args.ragas,
        )
