"""
Script test local không dùng Docker.
Chạy: python test_local.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("🧪 Testing RAG Student Handbook - Local Setup")
print("=" * 60)

# Test 1: Import config
print("\n1️⃣  Testing backend.config...")
try:
    from backend.config import settings
    print(f"   ✓ Config imported")
    print(f"   - LLM Model: {settings.LLM_MODEL}")
    print(f"   - Embedding Model: {settings.EMBEDDING_MODEL}")
    print(f"   - Qdrant Collection: {settings.QDRANT_COLLECTION}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Test 2: Import database models
print("\n2️⃣  Testing backend.db.models...")
try:
    from backend.db.models import User, ChatSession, ChatMessage
    print(f"   ✓ Models imported: User, ChatSession, ChatMessage")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Test 3: Import utilities
print("\n3️⃣  Testing backend.utils...")
try:
    from backend.utils import get_logger, HandbookException
    logger = get_logger("test")
    print(f"   ✓ Utils imported: get_logger, HandbookException")
    logger.info("Test log message")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Test 4: Import retrieval components
print("\n4️⃣  Testing backend.retrieval...")
try:
    from backend.retrieval.retriever import hybrid_search
    from backend.retrieval.bm25 import BM25Index
    from backend.retrieval.citation import CitationSource
    print(f"   ✓ Retrieval components imported")
    print(f"   - hybrid_search, BM25Index, CitationSource")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Test 5: Import LLM chain
print("\n5️⃣  Testing backend.llm.chains...")
try:
    from backend.llm.chains.rag_chain import HandbookAgent
    from backend.llm.chains.state import AgentState
    print(f"   ✓ LLM chain imported: HandbookAgent, AgentState")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Test 6: Import API
print("\n6️⃣  Testing backend.api...")
try:
    from backend.api.routes import chat_router, health_router
    from backend.api.schemas import ChatRequest
    print(f"   ✓ API components imported")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

# Test 7: Import main app
print("\n7️⃣  Testing main.py...")
try:
    from main import app
    print(f"   ✓ FastAPI app imported")
    print(f"   - App title: {app.title}")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ All imports successful!")
print("=" * 60)
print("\n📝 Next steps:")
print("1. Start Qdrant: docker run -p 6333:6333 qdrant/qdrant")
print("2. Start Redis: docker run -p 6379:6379 redis")
print("3. Start Postgres: docker run -p 5432:5432 -e POSTGRES_PASSWORD=xxx postgres")
print("4. Start Neo4j: docker run -p 7687:7687 neo4j")
print("5. Run app: uvicorn main:app --reload")
print("\nOr use docker-compose for all services:")
print("docker-compose up -d postgres redis qdrant neo4j")
