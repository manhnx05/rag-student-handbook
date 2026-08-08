"""
Qdrant client singleton — thread-safe lazy initialisation.

QdrantClient itself is thread-safe for concurrent requests once constructed;
this module just ensures the constructor is only called once per process.
"""
from __future__ import annotations

import threading
from typing import Optional

from qdrant_client import QdrantClient as _QdrantClient

from src.core.config import settings

_client_instance: Optional[_QdrantClient] = None
_client_lock = threading.Lock()


def get_qdrant_client() -> _QdrantClient:
    """Return a singleton Qdrant client connected to the configured URL.

    Uses double-checked locking to safely handle concurrent first-time calls
    from multiple threads.
    """
    global _client_instance
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                _client_instance = _QdrantClient(url=settings.QDRANT_URL)
    return _client_instance


def reset_qdrant_client() -> None:
    """Reset the singleton (intended for tests only)."""
    global _client_instance
    with _client_lock:
        _client_instance = None
