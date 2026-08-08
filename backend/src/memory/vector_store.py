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
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.core.config import settings
from src.core.logger import get_logger
from src.memory.embeddings import embed_text, embed_texts

logger = get_logger(__name__)

# Embedding dimension for text-embedding-3-small
_EMBEDDING_DIM = 1536


class VectorStore:
    def __init__(self) -> None:
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION
        self._ensure_collection_exists()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_collection_exists(self) -> None:
        """Create the Qdrant collection if it doesn't already exist."""
        try:
            self.client.get_collection(self.collection_name)
            logger.debug("Qdrant collection '%s' already exists", self.collection_name)
        except Exception:
            logger.info(
                "Qdrant collection '%s' not found — creating (dim=%d, cosine)",
                self.collection_name,
                _EMBEDDING_DIM,
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=_EMBEDDING_DIM,
                    distance=models.Distance.COSINE,
                ),
            )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[dict]) -> None:
        """Embed and upsert chunks into the vector store.

        Each chunk must have:
          - id       (str)  — unique identifier
          - content  (str)  — text to embed
          - metadata (dict, optional) — extra payload fields
        """
        if not chunks:
            return

        ids = [c["id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c.get("metadata", {}) for c in chunks]

        embeddings = embed_texts(documents)

        points = [
            models.PointStruct(
                id=ids[i],
                vector=embeddings[i],
                payload={"content": documents[i], **metadatas[i]},
            )
            for i in range(len(chunks))
        ]

        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info("Upserted %d chunks into Qdrant collection '%s'", len(chunks), self.collection_name)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(self, query_text: str, top_k: Optional[int] = None) -> dict:
        """Embed query and return the top-k most similar chunks.

        Returns a dict with keys: ids, documents, metadatas, distances
        (each value is a list-of-lists for ChromaDB API compatibility).
        """
        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        query_vector = embed_text(query_text)

        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
        )

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

    def count(self) -> int:
        """Return the number of vectors in the collection."""
        try:
            return self.client.count(collection_name=self.collection_name).count
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear_collection(self) -> None:
        """Drop and recreate the Qdrant collection (destructive)."""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            logger.warning("Dropped Qdrant collection '%s'", self.collection_name)
        except Exception:
            pass
        self._ensure_collection_exists()


# ---------------------------------------------------------------------------
# Thread-safe singleton
# ---------------------------------------------------------------------------
_instance: Optional[VectorStore] = None
_lock = threading.Lock()


def get_vector_store() -> VectorStore:
    """Return the process-level singleton VectorStore.

    Uses double-checked locking so concurrent first-time callers from
    different threads only construct the instance once.
    """
    global _instance
    if _instance is None:                    # fast path (no lock after init)
        with _lock:
            if _instance is None:            # re-check inside lock
                logger.info("Initialising VectorStore singleton…")
                _instance = VectorStore()
    return _instance


def reset_vector_store() -> None:
    """Replace the singleton with a fresh instance.

    Intended for tests that need a clean state between runs.
    """
    global _instance
    with _lock:
        _instance = None
