"""
Embeddings — thread-safe singleton for Gemini embedding model.
"""
from __future__ import annotations

import threading
from typing import Optional

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

_embedding_model: Optional[GoogleGenerativeAIEmbeddings] = None
_embedding_lock = threading.Lock()


def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
    """Return the cached GoogleGenerativeAIEmbeddings instance (thread-safe).

    Raises ValueError if GEMINI_API_KEY is not configured.
    """
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                if not settings.GEMINI_API_KEY:
                    raise ValueError(
                        "GEMINI_API_KEY must be set in environment variables or .env"
                    )
                logger.info(
                    "Initialising embedding model: %s", settings.EMBEDDING_MODEL
                )
                _embedding_model = GoogleGenerativeAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    google_api_key=settings.GEMINI_API_KEY,
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
