from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from qdrant_client.http import models

from backend.config import settings
from backend.vectordb.vector_store import VectorStore


@pytest.mark.asyncio
async def test_vector_store_creates_collection_with_configured_embedding_size():
    client = AsyncMock()
    client.get_collections.return_value = SimpleNamespace(collections=[])

    with patch(
        "backend.vectordb.vector_store.AsyncQdrantClient",
        return_value=client,
    ):
        store = VectorStore()

    await store.setup()

    client.create_collection.assert_awaited_once()
    request = client.create_collection.await_args.kwargs
    assert request["vectors_config"].size == settings.EMBEDDING_DIMENSION
    assert request["vectors_config"].distance is models.Distance.COSINE


@pytest.mark.asyncio
async def test_vector_store_adds_and_queries_chunks_without_blocking_event_loop():
    client = AsyncMock()
    point = SimpleNamespace(
        id="chunk-1",
        score=0.9,
        payload={"content": "Graduation requirements", "source": "handbook.pdf", "page": 2},
    )
    client.query_points.return_value = SimpleNamespace(points=[point])
    store = VectorStore()
    store.client = client
    chunks = [
        {
            "id": "chunk-1",
            "content": "Graduation requirements",
            "metadata": {"source": "handbook.pdf", "page": 2},
        }
    ]

    with (
        patch("backend.vectordb.vector_store.embed_texts", return_value=[[0.1] * 768]),
        patch("backend.vectordb.vector_store.embed_text", return_value=[0.2] * 768),
    ):
        await store.add_chunks(chunks)
        results = await store.query("graduation", top_k=1)

    client.upsert.assert_awaited_once()
    assert results["ids"] == [["chunk-1"]]
    assert results["documents"] == [["Graduation requirements"]]
    assert results["metadatas"] == [[{"source": "handbook.pdf", "page": 2}]]


@pytest.mark.asyncio
async def test_vector_store_rejects_collection_with_wrong_embedding_dimension():
    client = AsyncMock()
    client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name="student_handbook")]
    )
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=models.VectorParams(
                    size=settings.EMBEDDING_DIMENSION + 1,
                    distance=models.Distance.COSINE,
                )
            )
        )
    )
    store = VectorStore()
    store.client = client

    with pytest.raises(ValueError, match="EMBEDDING_DIMENSION"):
        await store.setup()
