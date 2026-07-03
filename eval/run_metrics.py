#!/usr/bin/env python3
"""Run automated retrieval metrics and optional RAGAS scoring on evaluation results."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.metrics.ragas_eval import print_ragas_summary, run_ragas_metrics
from eval.metrics.retrieval import compute_retrieval_metrics, print_retrieval_summary
from eval.run_evaluation import run_evaluation
from eval.scoring import load_evaluation, load_questions


def save_report(report: dict, output_dir: str) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_dir) / f"metrics_{timestamp}.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    return str(output_path)


def compare_reports(path_a: str, path_b: str) -> None:
    with open(path_a, encoding="utf-8") as handle:
        report_a = json.load(handle)
    with open(path_b, encoding="utf-8") as handle:
        report_b = json.load(handle)

    print("\n" + "=" * 60)
    print("METRICS COMPARISON")
    print("=" * 60)
    print(f"A: {path_a}")
    print(f"B: {path_b}")
    print("-" * 60)

    keys = ["recall_at_k", "document_recall_at_k", "mrr"]
    for key in keys:
        a_val = report_a.get("retrieval", {}).get(key)
        b_val = report_b.get("retrieval", {}).get(key)
        if a_val is not None and b_val is not None:
            delta = round(b_val - a_val, 4)
            sign = "+" if delta >= 0 else ""
            print(f"{key:22} {a_val} -> {b_val} ({sign}{delta})")

    ragas_a = report_a.get("ragas", {}).get("scores", {})
    ragas_b = report_b.get("ragas", {}).get("scores", {})
    if ragas_a and ragas_b:
        print("-" * 60)
        for metric in sorted(set(ragas_a) | set(ragas_b)):
            a_val = ragas_a.get(metric)
            b_val = ragas_b.get(metric)
            if a_val is not None and b_val is not None:
                delta = round(b_val - a_val, 4)
                sign = "+" if delta >= 0 else ""
                print(f"{metric:22} {a_val} -> {b_val} ({sign}{delta})")
    print("=" * 60 + "\n")


def run_metrics(
    input_file: str = "eval/evaluation_results.json",
    k: int = 5,
    run_ragas: bool = False,
    output_dir: str = "eval/reports",
) -> dict:
    results = load_evaluation(input_file)
    if not results:
        raise FileNotFoundError(
            f"No evaluation results at {input_file}. "
            "Run: python eval/run_evaluation.py"
        )

    questions = load_questions()
    questions_by_id = {question["id"]: question for question in questions}
    evaluations = [evaluation.model_dump() for evaluation in results.evaluations]

    retrieval = compute_retrieval_metrics(evaluations, questions_by_id, k=k)
    print_retrieval_summary(retrieval)

    ragas_report = None
    if run_ragas:
        try:
            ragas_report = run_ragas_metrics(evaluations, questions_by_id)
            print_ragas_summary(ragas_report)
        except Exception as exc:
            ragas_report = {"status": "error", "reason": str(exc)}
            print(f"RAGAS failed: {exc}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": input_file,
        "api_url": results.api_url,
        "top_k": results.top_k or k,
        "retrieval": retrieval,
        "ragas": ragas_report,
    }

    output_path = save_report(report, output_dir)
    print(f"Metrics report saved to: {output_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run retrieval and RAGAS metrics")
    parser.add_argument("--input", default="eval/evaluation_results.json")
    parser.add_argument("--k", type=int, default=5, help="k for Recall@k")
    parser.add_argument("--ragas", action="store_true", help="Run RAGAS (requires LLM_API_KEY)")
    parser.add_argument("--run-eval", action="store_true", help="Run API evaluation first")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--output-dir", default="eval/reports")
    parser.add_argument("--compare", nargs=2, metavar=("REPORT_A", "REPORT_B"))
    args = parser.parse_args()

    if args.compare:
        compare_reports(args.compare[0], args.compare[1])
        sys.exit(0)

    if args.run_eval:
        run_evaluation(
            api_url=args.api_url,
            top_k=args.top_k,
            include_answer=not args.retrieval_only,
            output_file=args.input,
        )

    try:
        run_metrics(
            input_file=args.input,
            k=args.k,
            run_ragas=args.ragas,
            output_dir=args.output_dir,
        )
    except FileNotFoundError as exc:
        print(exc)
        sys.exit(1)
