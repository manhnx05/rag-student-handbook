from qdrant_client import QdrantClient as _QdrantClient
from src.core.config import settings

_client_instance: _QdrantClient | None = None


def get_qdrant_client() -> _QdrantClient:
    """Return a singleton Qdrant client connected to the configured URL."""
    global _client_instance
    if _client_instance is None:
        _client_instance = _QdrantClient(url=settings.QDRANT_URL)
    return _client_instance
