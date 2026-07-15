import os
import pytest

os.environ["OPENAI_API_KEY"] = "sk-test12345678901234567890"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["LLM_MODEL"] = "gpt-4o-mini"

@pytest.fixture(autouse=True, scope="session")
def set_env_vars():
    pass
