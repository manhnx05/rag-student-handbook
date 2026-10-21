"""
VectorStore — Qdrant-backed vector store for semantic search.

The async Qdrant client is shared by a process-level singleton.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from backend.config import settings
from backend.utils.helpers import get_logger
from backend.embeddings.embedder import embed_text, embed_texts

logger = get_logger(__name__)


class VectorStore:
    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION

    async def close(self) -> None:
        """Close the Qdrant HTTP client."""
        await self.client.close()

    async def setup(self) -> None:
        """Create the collection or verify it matches the configured embedding size."""
        collections = await self.client.get_collections()
        collection_names = {collection.name for collection in collections.collections}
        if self.collection_name not in collection_names:
            logger.info(
                "Qdrant collection '%s' not found — creating (dim=%d, cosine)",
                self.collection_name,
                settings.EMBEDDING_DIMENSION,
            )
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=models.Distance.COSINE,
                ),
            )
            return

        collection = await self.client.get_collection(self.collection_name)
        vectors = collection.config.params.vectors
        if isinstance(vectors, dict):
            raise ValueError(
                f"Qdrant collection '{self.collection_name}' uses named vectors, "
                "but this vector store expects a single unnamed vector."
            )
        actual_dimension = getattr(vectors, "size", None)
        if actual_dimension != settings.EMBEDDING_DIMENSION:
            raise ValueError(
                f"Qdrant collection '{self.collection_name}' has vector size "
                f"{actual_dimension}, but EMBEDDING_DIMENSION is "
                f"{settings.EMBEDDING_DIMENSION}. Recreate/reindex the collection "
                "or configure the matching embedding dimension."
            )
        logger.debug("Qdrant collection '%s' is ready", self.collection_name)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    UPSERT_BATCH_SIZE = 200

    async def add_chunks(self, chunks: list[dict]) -> None:
        """Embed and upsert chunks into the vector store in batches."""
        if not chunks:
            return

        # Qdrant only accepts unsigned integers or UUIDs as point IDs; derive a
        # stable UUID from the human-readable chunk id.
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, c["id"])) for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c.get("metadata", {}) for c in chunks]

        embeddings = await asyncio.to_thread(embed_texts, documents)

        points = [
            models.PointStruct(
                id=ids[i],
                vector=embeddings[i],
                payload={**metadatas[i], "content": documents[i]},
            )
            for i in range(len(chunks))
        ]

        total_upserted = 0
        for batch_start in range(0, len(points), self.UPSERT_BATCH_SIZE):
            batch = points[batch_start : batch_start + self.UPSERT_BATCH_SIZE]
            await self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            total_upserted += len(batch)
            logger.debug(
                "Upserted batch %d/%d to Qdrant collection '%s'",
                total_upserted,
                len(points),
                self.collection_name,
            )

        logger.info(
            "Upserted %d chunks into Qdrant collection '%s'",
            total_upserted,
            self.collection_name,
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def query(self, query_text: str, top_k: Optional[int] = None) -> dict:
        """Embed query and return the top-k most similar chunks."""
        if top_k is None:
            top_k = settings.TOP_K_RESULTS
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        query_vector = await asyncio.to_thread(embed_text, query_text)
        # qdrant-client >= 1.10 replaced AsyncQdrantClient.search with query_points.
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
        )
        search_result = result.points

        ids, documents, metadatas, distances = [], [], [], []
        for point in search_result:
            ids.append(str(point.id))
            payload = point.payload or {}
            documents.append(payload.get("content", ""))
            metadatas.append({k: v for k, v in payload.items() if k != "content"})
            distances.append(point.score)

        return {
            "ids": [ids],
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    async def count(self) -> int:
        """Return the number of vectors in the collection."""
        res = await self.client.count(collection_name=self.collection_name)
        return res.count

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def clear_collection(self) -> None:
        """Drop and recreate the Qdrant collection (destructive)."""
        collections = await self.client.get_collections()
        if self.collection_name in {c.name for c in collections.collections}:
            await self.client.delete_collection(collection_name=self.collection_name)
            logger.warning("Dropped Qdrant collection '%s'", self.collection_name)
        await self.setup()


# ---------------------------------------------------------------------------
_instance: Optional[VectorStore] = None
_lock = asyncio.Lock()


async def get_vector_store() -> VectorStore:
    """Return the process-level singleton VectorStore."""
    global _instance
    if _instance is None:
        async with _lock:
            if _instance is None:
                logger.info("Initialising VectorStore singleton…")
                _instance = VectorStore()
                await _instance.setup()
    return _instance


async def reset_vector_store() -> None:
    """Replace the singleton with a fresh instance (intended for tests only)."""
    global _instance
    async with _lock:
        _instance = None
