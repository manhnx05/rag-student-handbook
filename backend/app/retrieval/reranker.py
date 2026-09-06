"""Reranking helpers for hybrid retrieval results."""
from __future__ import annotations

from typing import TypedDict

from app.keyword_search.bm25 import BM25Document, BM25Index


class RetrievedDocument(TypedDict):
    """Normalized retrieval result used between retrievers and the LLM."""

    content: str
    metadata: dict
    vector_rank: int


def rerank_documents(
    query: str,
    documents: list[RetrievedDocument],
    top_k: int | None = None,
) -> list[RetrievedDocument]:
    """Rerank vector results using lexical relevance without losing metadata."""
    if not documents:
        return []

    index = BM25Index(
        BM25Document(
            content=document["content"],
            metadata=document,
            index=document["vector_rank"],
        )
        for document in documents
    )
    ranked = index.search(query)
    return [document.metadata for document, _score in ranked[:top_k]]
