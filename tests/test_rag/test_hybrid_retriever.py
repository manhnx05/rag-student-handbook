from unittest.mock import AsyncMock

import pytest

from backend.config import settings
from backend.retrieval import retriever as hybrid_retriever
from backend.retrieval.citation import build_citations, format_citations
from backend.retrieval.retriever import rerank_documents


@pytest.mark.asyncio
async def test_hybrid_search_combines_vector_sources_and_graph_context(monkeypatch):
    vector_store = AsyncMock()
    vector_store.query.return_value = {
        "documents": [["Điều kiện xét tốt nghiệp"]],
        "metadatas": [[{"source": "handbook.pdf", "page": 12}]],
    }
    graph_store = AsyncMock()
    graph_store.query_graph.return_value = [
        {
            "node": {"name": "Tốt nghiệp"},
            "connections": [
                {"relation": "REQUIRES", "neighbor": "Hoàn thành chương trình"}
            ],
        }
    ]
    monkeypatch.setattr(
        hybrid_retriever,
        "get_vector_store",
        AsyncMock(return_value=vector_store),
    )
    monkeypatch.setattr(
        hybrid_retriever,
        "get_graph_store",
        AsyncMock(return_value=graph_store),
    )

    context = await hybrid_retriever.hybrid_search("điều kiện tốt nghiệp")

    assert "Điều kiện xét tốt nghiệp" in context
    assert "[1] handbook.pdf, page 12" in context
    assert "Tốt nghiệp: REQUIRES → Hoàn thành chương trình" in context
    vector_store.query.assert_awaited_once()
    # The dense search pulls a wide candidate pool (max(top_k, RETRIEVAL_RECALL_K)).
    vector_store.query.assert_awaited_once_with(
        "điều kiện tốt nghiệp",
        top_k=max(settings.TOP_K_RESULTS, settings.RETRIEVAL_RECALL_K),
    )
    graph_store.query_graph.assert_awaited_once_with(
        "điều kiện tốt nghiệp", top_k=settings.TOP_K_RESULTS
    )


@pytest.mark.asyncio
async def test_hybrid_search_returns_explicit_empty_context_when_both_sources_are_empty(monkeypatch):
    monkeypatch.setattr(
        hybrid_retriever,
        "_do_vector_search",
        AsyncMock(return_value=""),
    )
    monkeypatch.setattr(
        hybrid_retriever,
        "_do_graph_search",
        AsyncMock(return_value=""),
    )

    context = await hybrid_retriever.hybrid_search("unknown question")

    assert context == "No relevant information found in the handbook."


def test_rerank_documents_returns_empty_list_for_no_documents():
    assert rerank_documents("anything", []) == []


def test_rerank_documents_keeps_lexical_match_and_honours_top_k():
    documents = [
        {"content": "hoàn toàn không liên quan", "metadata": {}, "vector_rank": 0},
        {"content": "điều kiện tốt nghiệp", "metadata": {}, "vector_rank": 1},
        {"content": "một nội dung khác", "metadata": {}, "vector_rank": 2},
    ]

    ranked = rerank_documents("điều kiện tốt nghiệp", documents, top_k=2)

    assert len(ranked) == 2
    assert "điều kiện tốt nghiệp" in {document["content"] for document in ranked}


def test_build_citations_keeps_distinct_chunks_of_same_page():
    documents = [
        {
            "content": "Đoạn một về tốt nghiệp",
            "metadata": {"source": "handbook.pdf", "page": 12},
        },
        {
            "content": "Đoạn hai về tốt nghiệp",
            "metadata": {"source": "handbook.pdf", "page": 12},
        },
    ]

    citations = build_citations(documents)

    assert [citation.id for citation in citations] == [1, 2]
    assert all(citation.page == 12 for citation in citations)
    assert format_citations(citations).count("[1]") == 1

    # Identical (source, page, snippet) chunks are still de-duplicated.
    assert len(build_citations(documents + [documents[0]])) == 2
