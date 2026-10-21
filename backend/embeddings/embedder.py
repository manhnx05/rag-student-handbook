"""
Embeddings — thread-safe singleton for the local embedding model.

Embeddings run locally through sentence-transformers (CPU), so only the LLM
calls the Gemini API. `settings.EMBEDDING_MODEL` is a HuggingFace repo id, e.g.
"dangvantuan/vietnamese-embedding" (768 dimensions).
"""
from __future__ import annotations

import threading
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings

from backend.config import settings
from backend.utils.helpers import get_logger

logger = get_logger(__name__)

_embedding_model: Optional[HuggingFaceEmbeddings] = None
_embedding_lock = threading.Lock()

# The RoBERTa checkpoint behind `dangvantuan/vietnamese-embedding` only supports
# 258 positions (`max_position_embeddings`). sentence-transformers would otherwise
# truncate at 512 and raise "index 258 is out of bounds" on longer inputs.
MAX_SEQ_LENGTH = 256


def get_embedding_model() -> HuggingFaceEmbeddings:
    """Return the cached local embedding model (thread-safe)."""
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                logger.info(
                    "Initialising local embedding model: %s", settings.EMBEDDING_MODEL
                )
                model = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={"device": "cpu"},
                    # Cosine similarity in Qdrant expects normalised vectors.
                    encode_kwargs={"normalize_embeddings": True},
                )
                # Keep sentence-transformers' truncation within the checkpoint's
                # real position limit.
                client = getattr(model, "_client", None)
                if client is not None:
                    client.max_seq_length = MAX_SEQ_LENGTH
                _embedding_model = model
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """Embed a single text string and return its vector."""
    return get_embedding_model().embed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts and return their vectors."""
    return get_embedding_model().embed_documents(texts)


def reset_embedding_model() -> None:
    """Reset the cached model (intended for tests only)."""
    global _embedding_model
    with _embedding_lock:
        _embedding_model = None
