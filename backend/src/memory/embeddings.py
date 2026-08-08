"""
Embeddings — thread-safe singleton for OpenAI embedding model.

OpenAIEmbeddings is stateless (each call makes an HTTP request) so a single
cached instance is safe to share across threads.
"""
from __future__ import annotations

import threading
from typing import Optional

from langchain_openai import OpenAIEmbeddings

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

_embedding_model: Optional[OpenAIEmbeddings] = None
_embedding_lock = threading.Lock()


def get_embedding_model() -> OpenAIEmbeddings:
    """Return the cached OpenAIEmbeddings instance (thread-safe).

    Raises ValueError if OPENAI_API_KEY is not configured.
    """
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                if not settings.OPENAI_API_KEY:
                    raise ValueError(
                        "OPENAI_API_KEY must be set in environment variables or .env"
                    )
                logger.info(
                    "Initialising embedding model: %s", settings.EMBEDDING_MODEL
                )
                _embedding_model = OpenAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    openai_api_key=settings.OPENAI_API_KEY,
                )
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
