"""Thread and async-safety tests for RAG service singletons."""

from __future__ import annotations

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_async_singletons_use_asyncio_locks():
    from backend.retrieval import graph_store
    from backend.vectordb import vector_store

    assert isinstance(graph_store._graph_store_lock, asyncio.Lock)
    assert isinstance(vector_store._lock, asyncio.Lock)


def test_sync_singletons_use_thread_locks():
    from backend.embeddings import embedder
    from backend.vectordb import qdrant_client

    lock_type = type(threading.Lock())
    assert isinstance(embedder._embedding_lock, lock_type)
    assert isinstance(qdrant_client._client_lock, lock_type)


@pytest.mark.asyncio
async def test_vector_store_is_constructed_once_for_concurrent_async_callers():
    from backend.vectordb import vector_store as module

    await module.reset_vector_store()
    instance = MagicMock()
    instance.setup = AsyncMock()
    with patch.object(module, "VectorStore", return_value=instance) as constructor:
        results = await asyncio.gather(
            *(module.get_vector_store() for _ in range(20))
        )

    assert all(result is instance for result in results)
    constructor.assert_called_once_with()
    instance.setup.assert_awaited_once()
    await module.reset_vector_store()


@pytest.mark.asyncio
async def test_graph_store_is_constructed_once_for_concurrent_async_callers():
    from backend.retrieval import graph_store as module

    await module.reset_graph_store()
    instance = MagicMock()
    instance.connect = AsyncMock()
    instance.close = AsyncMock()
    with patch.object(module, "GraphStore", return_value=instance) as constructor:
        results = await asyncio.gather(
            *(module.get_graph_store() for _ in range(20))
        )

    assert all(result is instance for result in results)
    constructor.assert_called_once_with()
    instance.connect.assert_awaited_once()
    await module.reset_graph_store()


def test_embedding_model_is_constructed_once_for_concurrent_threads():
    from backend.embeddings import embedder as module

    module.reset_embedding_model()
    results = []
    errors = []

    with patch(
        "backend.embeddings.embedder.HuggingFaceEmbeddings",
        return_value=MagicMock(),
    ) as constructor:
        def worker():
            try:
                results.append(id(module.get_embedding_model()))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert errors == []
    assert len(set(results)) == 1
    constructor.assert_called_once()
    module.reset_embedding_model()
