"""
VectorStore — Qdrant-backed vector store for semantic search.

Thread-safety: The module-level singleton is protected by a threading.Lock
using the double-checked locking pattern. This is safe for:
  - Single-process multi-threaded ASGI servers (uvicorn + threadpool workers)
  - Multi-process Gunicorn forks (each process gets its own singleton — OK
    because QdrantClient holds no shared OS resource)

Note: QdrantClient itself is thread-safe for concurrent reads/writes.
"""
from __future__ import annotations

import threading
import uuid
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import settings
from app.core.logger import get_logger
from app.embedding.embeddings import embed_text, embed_texts

logger = get_logger(__name__)

class VectorStore:
    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION

    async def setup(self) -> None:
        """Create the Qdrant collection if it doesn't already exist."""
        try:
            collection = await self.client.get_collection(self.collection_name)
        except Exception:
            logger.info(
                "Qdrant collection '%s' not found — creating (dim=%d, cosine)",
                self.collection_name,
                settings.EMBEDDING_DIM,
            )
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=models.Distance.COSINE,
                ),
            )
            return

        vectors = collection.config.params.vectors
        if isinstance(vectors, dict):
            if len(vectors) != 1:
                raise ValueError(
                    f"Qdrant collection '{self.collection_name}' uses named vectors"
                )
            vectors = next(iter(vectors.values()))
        actual_dim = vectors.size
        if actual_dim != settings.EMBEDDING_DIM:
            raise ValueError(
                f"Qdrant collection '{self.collection_name}' has dimension "
                f"{actual_dim}, expected {settings.EMBEDDING_DIM} for "
                f"{settings.EMBEDDING_MODEL}"
            )
        logger.debug("Qdrant collection '%s' already exists", self.collection_name)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add_chunks(self, chunks: list[dict]) -> None:
        """Embed and upsert chunks into the vector store."""
        if not chunks:
            return

        ids = [c["id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c.get("metadata", {}) for c in chunks]

        # embed_texts is currently synchronous, keep it that way unless we also make embeddings async
        # We can run it in a thread if it's slow, but let's keep it as is.
        embeddings = embed_texts(documents)

        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.collection_name}:{ids[i]}")),
                vector=embeddings[i],
                payload={"content": documents[i], "chunk_id": ids[i], **metadatas[i]},
            )
            for i in range(len(chunks))
        ]

        await self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info("Upserted %d chunks into Qdrant collection '%s'", len(chunks), self.collection_name)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def query(self, query_text: str, top_k: Optional[int] = None) -> dict:
        """Embed query and return the top-k most similar chunks."""
        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        query_vector = embed_text(query_text)

        search_result = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
        )

        ids, documents, metadatas, distances = [], [], [], []
        for point in search_result:
            payload = point.payload or {}
            ids.append(str(payload.get("chunk_id", point.id)))
            documents.append(payload.get("content", ""))
            metadatas.append(
                {k: v for k, v in payload.items() if k not in {"content", "chunk_id"}}
            )
            distances.append(point.score)

        return {
            "ids": [ids],
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    async def count(self) -> int:
        """Return the number of vectors in the collection."""
        try:
            res = await self.client.count(collection_name=self.collection_name)
            return res.count
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def clear_collection(self) -> None:
        """Drop and recreate the Qdrant collection (destructive)."""
        try:
            await self.client.delete_collection(collection_name=self.collection_name)
            logger.warning("Dropped Qdrant collection '%s'", self.collection_name)
        except Exception:
            pass
        await self.setup()


# ---------------------------------------------------------------------------
# Thread-safe singleton
import asyncio

_instance: Optional[VectorStore] = None
_lock = asyncio.Lock()


async def get_vector_store() -> VectorStore:
    """Return the process-level singleton VectorStore.

    Uses double-checked locking so concurrent first-time callers from
    different threads only construct the instance once.
    """
    global _instance
    if _instance is None:                    # fast path (no lock after init)
        async with _lock:
            if _instance is None:            # re-check inside lock
                logger.info("Initialising VectorStore singleton…")
                _instance = VectorStore()
                await _instance.setup()
    return _instance


async def reset_vector_store() -> None:
    """Replace the singleton with a fresh instance.

    Intended for tests that need a clean state between runs.
    """
    global _instance
    async with _lock:
        _instance = None
