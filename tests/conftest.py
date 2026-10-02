"""Default non-secret settings for tests that import application modules."""

import os
import sys
from pathlib import Path

PYTHON_SOURCE = Path(__file__).resolve().parents[1] / "src" / "main" / "python"
sys.path.insert(0, str(PYTHON_SOURCE))

os.environ.setdefault("GEMINI_API_KEY", "test-gemini-api-key")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test"
)
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test-password")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:8501")
