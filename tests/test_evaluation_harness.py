"""Tests for the retrieval evaluation harness pure functions.

These tests use hand-written fake ``RetrievedDocument`` objects and the real
on-disk dataset loaders — no Qdrant, no network.
"""

from __future__ import annotations

from backend.evaluation.harness import (
    covers_topics,
    load_ground_truth,
    load_questions,
    score_question,
    topic_match,
)


def _doc(content: str, page: int | None = None, rank: int = 0) -> dict:
    metadata: dict = {"source": "handbook.pdf"}
    if page is not None:
        metadata["page"] = page
    return {"content": content, "metadata": metadata, "vector_rank": rank}


# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------

def test_load_questions_reads_dataset():
    questions = load_questions()
    assert questions
    assert {"id", "question", "source_topics"} <= set(questions[0])


def test_load_ground_truth_indexes_by_question_id():
    ground_truth = load_ground_truth()
    assert "q001" in ground_truth
    assert ground_truth["q001"]["source"] == "handbook.pdf"


# ---------------------------------------------------------------------------
# topic_match / covers_topics
# ---------------------------------------------------------------------------

def test_topic_match_full_and_partial_overlap():
    assert topic_match(
        "Điều kiện xét tốt nghiệp của sinh viên",
        "điều kiện xét tốt nghiệp",
    )
    assert not topic_match("Học phí và học bổng", "điều kiện xét tốt nghiệp")
    # Relaxed ratio accepts a partial overlap.
    assert topic_match("xét tốt nghiệp", "xét tốt nghiệp", ratio=0.5)


def test_topic_match_with_empty_topic_is_false():
    assert topic_match("Bất kỳ nội dung", "") is False


def test_covers_topics_matches_any_topic():
    topics = ["đăng ký học lại", "học cải thiện điểm"]
    assert covers_topics("Thủ tục học cải thiện điểm nằm ở đây", topics)
    assert not covers_topics("Nội dung hoàn toàn không liên quan", topics)


# ---------------------------------------------------------------------------
# score_question
# ---------------------------------------------------------------------------

def test_score_question_reports_mrr_for_first_relevant_chunk():
    documents = [
        _doc("Không liên quan", page=1, rank=0),
        _doc("Điều kiện xét tốt nghiệp", page=2, rank=1),
    ]

    scores = score_question(documents, ["điều kiện xét tốt nghiệp"], k=3)

    assert scores["hit"] is True
    assert scores["reciprocal_rank"] == 0.5
    assert scores["retrieved"] == 2
    assert scores["page_coverage"] == 1.0


def test_score_question_computes_page_coverage():
    documents = [
        _doc("Điều kiện xét tốt nghiệp", page=2, rank=0),
        _doc("Một đoạn khác", rank=1),  # missing page
        _doc("Đoạn thứ ba", page=9, rank=2),
    ]

    scores = score_question(documents, ["điều kiện xét tốt nghiệp"], k=3)

    assert scores["hit"] is True
    assert scores["reciprocal_rank"] == 1.0
    assert scores["retrieved"] == 3
    assert scores["page_coverage"] == 2 / 3


def test_score_question_without_hit_returns_zero_scores():
    documents = [_doc("Nội dung không liên quan", rank=0)]

    scores = score_question(documents, ["điều kiện xét tốt nghiệp"], k=3)

    assert scores["hit"] is False
    assert scores["reciprocal_rank"] == 0.0
    assert scores["retrieved"] == 1
    assert scores["page_coverage"] == 0.0


def test_score_question_only_considers_first_k_documents():
    documents = [
        _doc("Không liên quan", rank=0),
        _doc("Điều kiện xét tốt nghiệp", rank=1),
    ]

    scores = score_question(documents, ["điều kiện xét tốt nghiệp"], k=1)

    assert scores["hit"] is False
    assert scores["retrieved"] == 1
