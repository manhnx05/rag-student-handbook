"""Retrieval evaluation harness for data/evaluation.

Measures retrieval quality against the handbook ground-truth set so changes to
chunking/retrieval can be compared before and after:

  - hit@k : a retrieved chunk covers the expected topic
  - MRR   : rank of the first chunk that covers it
  - page coverage : share of retrieved chunks that carry a page number
    (a proxy for citation quality)

Usage:
  uv run python -m backend.evaluation.harness --mode both
  uv run python -m backend.evaluation.harness --mode hybrid --top-k 5 --output data/evaluation/report.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.retrieval.bm25 import tokenize
from backend.retrieval.retriever import RetrievedDocument, rerank_documents
from backend.utils.helpers import get_logger
from backend.vectordb.vector_store import get_vector_store

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "evaluation"
QUESTIONS_PATH = DATA_DIR / "questions.json"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"

# A chunk counts as covering a topic when it contains this share of the topic tokens.
TOPIC_MATCH_RATIO = 0.8


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_questions(path: Path = QUESTIONS_PATH) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_ground_truth(path: Path = GROUND_TRUTH_PATH) -> dict[str, dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        records = json.load(handle)
    return {record["question_id"]: record for record in records}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def topic_match(content: str, topic: str, ratio: float = TOPIC_MATCH_RATIO) -> bool:
    """True when `content` contains enough tokens of `topic`."""
    topic_tokens = tokenize(topic)
    if not topic_tokens:
        return False
    content_tokens = set(tokenize(content))
    matched = sum(1 for token in topic_tokens if token in content_tokens)
    return matched / len(topic_tokens) >= ratio


def covers_topics(content: str, topics: list[str]) -> bool:
    return any(topic_match(content, topic) for topic in topics)


def score_question(
    documents: list[RetrievedDocument],
    topics: list[str],
    k: int,
) -> dict[str, Any]:
    """Compute hit@k, reciprocal rank and page coverage for one question."""
    contents = [document["content"] for document in documents[:k]]

    hit = False
    reciprocal_rank = 0.0
    for rank, content in enumerate(contents, start=1):
        if covers_topics(content, topics):
            hit = True
            reciprocal_rank = 1.0 / rank
            break

    pages = [
        document["metadata"].get("page")
        for document in documents[:k]
        if document["metadata"].get("page") is not None
    ]

    return {
        "hit": hit,
        "reciprocal_rank": reciprocal_rank,
        "retrieved": len(contents),
        "page_coverage": len(pages) / len(contents) if contents else 0.0,
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

async def retrieve(
    query: str,
    mode: str,
    top_k: int,
    recall_k: int,
) -> list[RetrievedDocument]:
    """Run dense-only or hybrid retrieval and return the final ranking."""
    vector_store = await get_vector_store()
    results = await vector_store.query(query, top_k=recall_k)
    contents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    candidates: list[RetrievedDocument] = [
        {
            "content": content,
            "metadata": metadatas[index] if index < len(metadatas) else {},
            "vector_rank": index,
        }
        for index, content in enumerate(contents)
    ]

    if mode == "hybrid":
        return rerank_documents(query, candidates, top_k=top_k)
    return candidates[:top_k]


async def evaluate(
    mode: str,
    top_k: int | None = None,
    recall_k: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run the evaluation set and aggregate the metrics for one mode."""
    top_k = top_k or settings.TOP_K_RESULTS
    recall_k = max(recall_k or settings.RETRIEVAL_RECALL_K, top_k)

    questions = load_questions()
    if limit:
        questions = questions[:limit]

    per_question: list[dict[str, Any]] = []
    for item in questions:
        started = time.perf_counter()
        documents = await retrieve(item["question"], mode, top_k, recall_k)
        latency_ms = (time.perf_counter() - started) * 1000

        scores = score_question(documents, item.get("source_topics", []), top_k)
        per_question.append(
            {
                "id": item["id"],
                "question": item["question"],
                "latency_ms": round(latency_ms, 1),
                **scores,
            }
        )

    count = len(per_question) or 1
    return {
        "mode": mode,
        "top_k": top_k,
        "recall_k": recall_k,
        "questions": len(per_question),
        "hit_rate": sum(q["hit"] for q in per_question) / count,
        "mrr": sum(q["reciprocal_rank"] for q in per_question) / count,
        "page_coverage": sum(q["page_coverage"] for q in per_question) / count,
        "avg_latency_ms": sum(q["latency_ms"] for q in per_question) / count,
        "details": per_question,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_report(report: dict[str, Any]) -> None:
    print(
        f"[{report['mode']}] top_k={report['top_k']} recall_k={report['recall_k']} "
        f"questions={report['questions']}"
    )
    print(f"  hit@{report['top_k']:<3}        : {report['hit_rate']:.2%}")
    print(f"  MRR              : {report['mrr']:.3f}")
    print(f"  page coverage    : {report['page_coverage']:.2%}")
    print(f"  avg latency      : {report['avg_latency_ms']:.1f} ms")
    if report["questions"] and report["hit_rate"] == 0.0:
        print(
            "  ! No expected topic found in any result — check that the handbook "
            "has been ingested into Qdrant."
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate handbook retrieval quality")
    parser.add_argument("--mode", choices=["dense", "hybrid", "both"], default="both")
    parser.add_argument("--top-k", type=int, default=None, help="Chunks kept per question")
    parser.add_argument(
        "--recall-k", type=int, default=None, help="Candidates pulled before reranking"
    )
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate N questions")
    parser.add_argument("--output", type=Path, default=None, help="Write the report as JSON")
    args = parser.parse_args()

    modes = ["dense", "hybrid"] if args.mode == "both" else [args.mode]
    reports = []
    for mode in modes:
        report = await evaluate(mode, args.top_k, args.recall_k, args.limit)
        _print_report(report)
        reports.append(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(reports, handle, ensure_ascii=False, indent=2)
        print(f"Report written to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
