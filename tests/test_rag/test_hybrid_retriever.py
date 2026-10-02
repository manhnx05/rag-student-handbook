from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.rag.retrievers import hybrid_retriever


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
