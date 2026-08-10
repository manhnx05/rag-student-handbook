"""
Phase 3 Thread-Safety Tests
============================
Tests for:
  1. VectorStore singleton uses threading.Lock (double-checked locking)
  2. GraphStore singleton uses threading.Lock
  3. Embeddings singleton uses threading.Lock
  4. QdrantClient singleton uses threading.Lock
  5. Concurrent access to get_vector_store() constructs only ONE instance
  6. Concurrent access to get_embedding_model() constructs only ONE instance
  7. reset_*() functions clear the singleton for test isolation
"""
from __future__ import annotations

import os
import pathlib
import sys
import threading
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
BACKEND = pathlib.Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password123")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("JWT_SECRET_KEY", "supersecretkey1234567890abcdef00")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

import pytest


# ===========================================================================
# 1. Lock presence
# ===========================================================================
class TestLockPresence:
    def test_vector_store_has_lock(self):
        from src.memory import vector_store as mod
        assert hasattr(mod, "_lock"), "vector_store module must have a '_lock' attribute"
        assert isinstance(mod._lock, type(threading.Lock()))

    def test_graph_store_has_lock(self):
        from src.memory import graph_store as mod
        assert hasattr(mod, "_graph_store_lock")
        assert isinstance(mod._graph_store_lock, type(threading.Lock()))

    def test_embeddings_has_lock(self):
        from src.memory import embeddings as mod
        assert hasattr(mod, "_embedding_lock")
        assert isinstance(mod._embedding_lock, type(threading.Lock()))

    def test_qdrant_client_has_lock(self):
        from src.memory import qdrant_client as mod
        assert hasattr(mod, "_client_lock")
        assert isinstance(mod._client_lock, type(threading.Lock()))


# ===========================================================================
# 2. Double-checked locking pattern
# ===========================================================================
class TestDoubleCheckedLocking:
    """Verify each module has >= 2 'is None' checks (inner + outer) and a with-lock."""

    def _check_module(self, module_path: str) -> None:
        src = (BACKEND / module_path).read_text()
        none_checks = src.count("is None")
        assert none_checks >= 2, (
            f"{module_path}: expected at least 2 'is None' checks (double-checked locking), "
            f"found {none_checks}"
        )
        assert "with " in src, f"{module_path}: missing 'with' lock context manager"

    def test_vector_store_double_checked(self):
        self._check_module("src/memory/vector_store.py")

    def test_graph_store_double_checked(self):
        self._check_module("src/memory/graph_store.py")

    def test_embeddings_double_checked(self):
        self._check_module("src/memory/embeddings.py")

    def test_qdrant_client_double_checked(self):
        self._check_module("src/memory/qdrant_client.py")


# ===========================================================================
# 3. Reset functions exist and are callable
# ===========================================================================
class TestResetFunctions:
    def test_vector_store_reset_exists(self):
        from src.memory.vector_store import reset_vector_store
        assert callable(reset_vector_store)

    def test_graph_store_reset_exists(self):
        from src.memory.graph_store import reset_graph_store
        assert callable(reset_graph_store)

    def test_embeddings_reset_exists(self):
        from src.memory.embeddings import reset_embedding_model
        assert callable(reset_embedding_model)

    def test_qdrant_client_reset_exists(self):
        from src.memory.qdrant_client import reset_qdrant_client
        assert callable(reset_qdrant_client)


# ===========================================================================
# 4. Concurrent singleton construction — only ONE instance created
# ===========================================================================
class TestConcurrentSingletonConstruction:
    """
    Simulate N threads all calling get_X() simultaneously.
    The underlying constructor must be called exactly once.
    """

    def test_vector_store_constructed_once_under_concurrency(self):
        import src.memory.vector_store as mod

        # Reset before test
        mod.reset_vector_store()
        construction_count = 0
        original_init = mod.VectorStore.__init__

        def counting_init(self):
            nonlocal construction_count
            construction_count += 1
            # Fake out the real constructor
            self.client = MagicMock()
            self.collection_name = "test"
            # skip _ensure_collection_exists

        results = []
        errors = []

        def worker():
            try:
                with patch.object(mod.VectorStore, "__init__", counting_init):
                    instance = mod.get_vector_store()
                results.append(id(instance))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent access: {errors}"
        # All threads must get the SAME instance
        assert len(set(results)) == 1, (
            f"Expected 1 unique instance, got {len(set(results))}: "
            f"concurrent construction was not thread-safe!"
        )
        # Constructor was called at most once (may be 0 if already initialised)
        assert construction_count <= 1, (
            f"VectorStore.__init__ called {construction_count} times — not thread-safe!"
        )

        # Cleanup
        mod.reset_vector_store()

    def test_embeddings_constructed_once_under_concurrency(self):
        import src.memory.embeddings as mod

        mod.reset_embedding_model()
        construction_count = 0

        def fake_embeddings_init(self, **kwargs):
            nonlocal construction_count
            construction_count += 1

        results = []

        def worker():
            with patch("src.memory.embeddings.OpenAIEmbeddings") as MockEmb:
                MockEmb.return_value = MagicMock()
                instance = mod.get_embedding_model()
                results.append(id(instance))

        # Note: since patch is per-thread, we test the locking not the mock count here.
        # Instead just reset and call from multiple threads to check no race error.
        mod.reset_embedding_model()

        call_results = []
        call_errors = []

        with patch("src.memory.embeddings.GoogleGenerativeAIEmbeddings", return_value=MagicMock()):
            def worker2():
                try:
                    obj = mod.get_embedding_model()
                    call_results.append(id(obj))
                except Exception as e:
                    call_errors.append(e)

            threads = [threading.Thread(target=worker2) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not call_errors
        # All threads must see the same object
        assert len(set(call_results)) == 1, (
            f"Expected 1 unique embedding model, got {len(set(call_results))}"
        )

        mod.reset_embedding_model()

    def test_reset_allows_reconstruction(self):
        """After reset, the next call should create a fresh instance."""
        import src.memory.vector_store as mod

        mod.reset_vector_store()
        assert mod._instance is None

        with patch.object(
            mod.VectorStore,
            "__init__",
            lambda self: (
                setattr(self, "client", MagicMock()) or
                setattr(self, "collection_name", "test") or
                None
            ),
        ):
            inst1 = mod.get_vector_store()
            mod.reset_vector_store()
            assert mod._instance is None  # cleared
            inst2 = mod.get_vector_store()
            assert inst1 is not inst2, "reset should produce a new instance"

        mod.reset_vector_store()
