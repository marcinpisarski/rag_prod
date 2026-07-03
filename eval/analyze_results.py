#!/usr/bin/env python3
"""Analyze evaluation results and display summary."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

from eval.scoring import load_evaluation, print_evaluation_summary, print_scoring_guide


def citation_quote(citation: dict) -> str:
    return citation.get("quote") or citation.get("excerpt") or "N/A"


def citation_chunk_id(citation: dict) -> str:
    value = citation.get("chunk_id", citation.get("segment_id"))
    return str(value) if value is not None else "N/A"


def analyze_results(file_path: str = "eval/evaluation_results.json"):
    results = load_evaluation(file_path)
    if not results:
        print(f"No evaluation results found at: {file_path}")
        print("Run evaluation first: python eval/run_evaluation.py")
        return

    print_evaluation_summary(results)

    incomplete = [e for e in results.evaluations if not e.is_complete]
    if incomplete:
        print(f"{len(incomplete)} evaluations still need scoring:")
        for evaluation in incomplete[:5]:
            print(f"  - {evaluation.question_id}: {evaluation.question[:50]}...")
        if len(incomplete) > 5:
            print(f"  ... and {len(incomplete) - 5} more")
    else:
        print("All evaluations have been scored.")

    scored = [e for e in results.evaluations if e.is_complete]
    if scored:
        print("\n" + "=" * 60)
        print("TOP 5 BEST PERFORMING QUESTIONS")
        print("=" * 60)
        for index, evaluation in enumerate(
            sorted(scored, key=lambda item: item.total_score, reverse=True)[:5], 1
        ):
            print(f"\n{index}. {evaluation.question_id} (Score: {evaluation.total_score}/6)")
            print(f"   Q: {evaluation.question[:60]}...")
            print(
                f"   Correctness: {evaluation.correctness}, "
                f"Citations: {evaluation.citation_quality}, "
                f"Completeness: {evaluation.completeness}"
            )

        print("\n" + "=" * 60)
        print("BOTTOM 5 WORST PERFORMING QUESTIONS")
        print("=" * 60)
        for index, evaluation in enumerate(sorted(scored, key=lambda item: item.total_score)[:5], 1):
            print(f"\n{index}. {evaluation.question_id} (Score: {evaluation.total_score}/6)")
            print(f"   Q: {evaluation.question[:60]}...")
            print(
                f"   Correctness: {evaluation.correctness}, "
                f"Citations: {evaluation.citation_quality}, "
                f"Completeness: {evaluation.completeness}"
            )
            if evaluation.notes:
                print(f"   Notes: {evaluation.notes}")

    print("\n" + "=" * 60)
    print(f"Full results: {file_path}")
    print("=" * 60 + "\n")


def show_question_detail(question_id: str, file_path: str = "eval/evaluation_results.json"):
    results = load_evaluation(file_path)
    if not results:
        print("No evaluation results found")
        return

    evaluation = next((e for e in results.evaluations if e.question_id == question_id), None)
    if not evaluation:
        print(f"Question {question_id} not found")
        return

    print("\n" + "=" * 60)
    print(f"QUESTION DETAIL: {evaluation.question_id}")
    print("=" * 60)
    print(f"\nQuestion: {evaluation.question}")
    print(f"Expected: {evaluation.expected}")
    print(f"Category: {evaluation.category or 'n/a'} | Document: {evaluation.document or 'n/a'}")
    print(f"\nAnswer:\n{evaluation.answer}")
    print(f"\nCitations ({len(evaluation.citations)}):")
    for index, citation in enumerate(evaluation.citations, 1):
        print(f"\n  [{index}] Document: {citation.get('document_title', 'N/A')}")
        print(f"      Page: {citation.get('page_number', 'N/A')}, Chunk: {citation_chunk_id(citation)}")
        print(f"      Quote: {citation_quote(citation)[:120]}...")

    if evaluation.retrieval_results:
        print(f"\nRetrieval preview ({len(evaluation.retrieval_results)} segments):")
        for index, result in enumerate(evaluation.retrieval_results[:3], 1):
            print(
                f"  [{index}] seg={result.get('segment_id')} "
                f"score={result.get('similarity_score', 0):.3f} "
                f"page={result.get('page_number')}"
            )
            print(f"      {result.get('text', '')[:120]}...")

    print(f"\nContext available: {'Yes' if evaluation.has_sufficient_context else 'No'}")
    if evaluation.is_complete:
        print("\nScores:")
        print(f"  Correctness:      {evaluation.correctness}/2")
        print(f"  Citation Quality: {evaluation.citation_quality}/2")
        print(f"  Completeness:     {evaluation.completeness}/2")
        print(f"  TOTAL:            {evaluation.total_score}/6")
        if evaluation.notes:
            print(f"\nNotes: {evaluation.notes}")
    else:
        print("\nNot yet scored")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze RAG evaluation results")
    parser.add_argument("--file", default="eval/evaluation_results.json")
    parser.add_argument("--question", help="Show details for a question ID, e.g. q01")
    parser.add_argument("--guide", action="store_true", help="Show scoring guide")
    args = parser.parse_args()

    if args.guide:
        print_scoring_guide()
    elif args.question:
        show_question_detail(args.question, args.file)
    else:
        analyze_results(args.file)
