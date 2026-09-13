import os
import pytest

os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "test-password"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["LLM_MODEL"] = "gemini-1.5-flash"

@pytest.fixture(autouse=True, scope="session")
def set_env_vars():
    pass
