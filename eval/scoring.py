"""
Manual evaluation system for RAG with citations.

Scoring (0-6 points per question):
- Correctness (0-2): accuracy of the answer
- Grounding/Citations (0-2): quality of citations
- Completeness (0-2): answer completeness

Total: 30 questions x 6 points = 180 points max
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import json
from pathlib import Path


class QuestionEvaluation(BaseModel):
    """Single question evaluation"""
    question_id: str
    question: str
    expected: str
    answer: str
    citations: List[Dict]
    has_sufficient_context: bool
    category: Optional[str] = None
    document: Optional[str] = None
    retrieval_results: Optional[List[Dict]] = None

    correctness: Optional[int] = Field(None, ge=0, le=2)
    citation_quality: Optional[int] = Field(None, ge=0, le=2)
    completeness: Optional[int] = Field(None, ge=0, le=2)
    notes: Optional[str] = None

    @property
    def total_score(self) -> Optional[int]:
        if all(s is not None for s in [self.correctness, self.citation_quality, self.completeness]):
            return self.correctness + self.citation_quality + self.completeness
        return None

    @property
    def is_complete(self) -> bool:
        return all(s is not None for s in [self.correctness, self.citation_quality, self.completeness])


class EvaluationResults(BaseModel):
    """Complete evaluation results"""
    evaluations: List[QuestionEvaluation]
    api_url: Optional[str] = None
    top_k: Optional[int] = None
    include_answer: Optional[bool] = None

    @property
    def completed_count(self) -> int:
        return sum(1 for e in self.evaluations if e.is_complete)

    @property
    def total_questions(self) -> int:
        return len(self.evaluations)

    @property
    def total_score(self) -> int:
        return sum(e.total_score for e in self.evaluations if e.total_score is not None)

    @property
    def max_possible_score(self) -> int:
        return self.completed_count * 6

    @property
    def percentage(self) -> Optional[float]:
        if self.max_possible_score > 0:
            return (self.total_score / self.max_possible_score) * 100
        return None

    @property
    def avg_correctness(self) -> Optional[float]:
        scores = [e.correctness for e in self.evaluations if e.correctness is not None]
        return sum(scores) / len(scores) if scores else None

    @property
    def avg_citation_quality(self) -> Optional[float]:
        scores = [e.citation_quality for e in self.evaluations if e.citation_quality is not None]
        return sum(scores) / len(scores) if scores else None

    @property
    def avg_completeness(self) -> Optional[float]:
        scores = [e.completeness for e in self.evaluations if e.completeness is not None]
        return sum(scores) / len(scores) if scores else None

    def get_summary(self) -> Dict:
        return {
            "total_questions": self.total_questions,
            "completed_evaluations": self.completed_count,
            "total_score": self.total_score,
            "max_possible_score": self.max_possible_score,
            "percentage": round(self.percentage, 2) if self.percentage else None,
            "averages": {
                "correctness": round(self.avg_correctness, 2) if self.avg_correctness else None,
                "citation_quality": round(self.avg_citation_quality, 2) if self.avg_citation_quality else None,
                "completeness": round(self.avg_completeness, 2) if self.avg_completeness else None,
            },
            "breakdown": self._get_score_breakdown(),
        }

    def _get_score_breakdown(self) -> Dict:
        breakdown = {
            "correctness": {"0": 0, "1": 0, "2": 0},
            "citation_quality": {"0": 0, "1": 0, "2": 0},
            "completeness": {"0": 0, "1": 0, "2": 0},
        }
        for e in self.evaluations:
            if e.correctness is not None:
                breakdown["correctness"][str(e.correctness)] += 1
            if e.citation_quality is not None:
                breakdown["citation_quality"][str(e.citation_quality)] += 1
            if e.completeness is not None:
                breakdown["completeness"][str(e.completeness)] += 1
        return breakdown


def load_questions(file_path: str = "eval/questions.jsonl") -> List[Dict]:
    questions = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def save_evaluation(results: EvaluationResults, file_path: str = "eval/evaluation_results.json"):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(results.model_dump(), f, indent=2, ensure_ascii=False)


def load_evaluation(file_path: str = "eval/evaluation_results.json") -> Optional[EvaluationResults]:
    path = Path(file_path)
    if not path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return EvaluationResults(**json.load(f))


def print_evaluation_summary(results: EvaluationResults):
    summary = results.get_summary()

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Questions: {summary['total_questions']}")
    print(f"Completed Evaluations: {summary['completed_evaluations']}")
    print(f"Total Score: {summary['total_score']} / {summary['max_possible_score']}")
    if summary["percentage"] is not None:
        print(f"Percentage: {summary['percentage']}%")
    else:
        print("Percentage: N/A")

    print("\n" + "-" * 60)
    print("AVERAGE SCORES (out of 2):")
    for key, label in [
        ("correctness", "Correctness"),
        ("citation_quality", "Citation Quality"),
        ("completeness", "Completeness"),
    ]:
        value = summary["averages"][key]
        print(f"  {label + ':':18} {value:.2f}" if value is not None else f"  {label + ':':18} N/A")

    print("\n" + "-" * 60)
    print("SCORE DISTRIBUTION:")
    breakdown = summary["breakdown"]
    for category, labels in [
        ("correctness", ("Incorrect", "Partial", "Correct")),
        ("citation_quality", ("No/Bad", "Weak", "Strong")),
        ("completeness", ("Incomplete", "Mostly", "Complete")),
    ]:
        print(f"\n{category.replace('_', ' ').title()}:")
        for score, label in enumerate(labels):
            print(f"  {score} ({label}):{' ' * (12 - len(label))} {breakdown[category][str(score)]}")
    print("=" * 60 + "\n")


def print_scoring_guide():
    print("\n" + "=" * 60)
    print("SCORING GUIDE")
    print("=" * 60)
    print("\n1. CORRECTNESS (0-2 points):")
    print("   0 = Incorrect answer or hallucination")
    print("   1 = Partially correct")
    print("   2 = Correct answer")
    print("\n2. GROUNDING/CITATIONS (0-2 points):")
    print("   0 = No citations or irrelevant citations")
    print("   1 = Citations present but weak/imprecise")
    print("   2 = Citations accurate and support the answer")
    print("\n3. COMPLETENESS (0-2 points):")
    print("   0 = Missing key elements")
    print("   1 = Contains most information")
    print("   2 = Complete answer")
    print("\nMAX SCORE PER QUESTION: 6 points")
    print("MAX TOTAL SCORE (30 questions): 180 points")
    print("=" * 60 + "\n")
