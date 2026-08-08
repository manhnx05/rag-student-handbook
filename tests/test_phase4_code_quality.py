"""
Phase 4 Code Quality Tests
===========================
Tests for:
  1. state_manager.py is deleted (dead code removed)
  2. ChatService: get_user_sessions has limit/offset pagination params
  3. ChatService: SESSION_TITLE_MAX_LEN constant = 60
  4. ChatService: title truncated with ellipsis for long questions
  5. ChatService: short questions stored as-is (no truncation)
  6. ChatService: limit capped at 200 internally
  7. GET /sessions route has limit/offset Query params
  8. Chat route: no bare traceback.print_exc in executable code (AST check)
  9. VectorStore: no bare print() calls (all replaced with logger)
 10. GraphStore: no bare print() calls
 11. IngestionService: no bare print() calls
"""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import inspect
import os
import pathlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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


def _ast_has_print_call(source: str) -> bool:
    """Return True if the source contains a bare print() call (not in a string/comment)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                return True
    return False


def _ast_has_traceback_print_exc(source: str) -> bool:
    """Return True if source contains traceback.print_exc() call in executable code."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "print_exc"
                and isinstance(func.value, ast.Name)
                and func.value.id == "traceback"
            ):
                return True
    return False


# ===========================================================================
# 1. Dead code removal
# ===========================================================================
class TestDeadCodeRemoval:
    def test_state_manager_deleted(self):
        spec = importlib.util.find_spec("src.orchestration.state_manager")
        assert spec is None, (
            "state_manager.py should be deleted — it is dead code with no callers"
        )

    def test_state_manager_file_not_on_disk(self):
        path = BACKEND / "src" / "orchestration" / "state_manager.py"
        assert not path.exists(), f"state_manager.py still exists at {path}"


# ===========================================================================
# 2. ChatService pagination
# ===========================================================================
class TestChatServicePagination:
    def test_get_user_sessions_has_limit_param(self):
        from src.services.chat_service import ChatService
        sig = inspect.signature(ChatService.get_user_sessions)
        assert "limit" in sig.parameters, "get_user_sessions missing 'limit' parameter"

    def test_get_user_sessions_has_offset_param(self):
        from src.services.chat_service import ChatService
        sig = inspect.signature(ChatService.get_user_sessions)
        assert "offset" in sig.parameters, "get_user_sessions missing 'offset' parameter"

    def test_get_user_sessions_limit_default_50(self):
        from src.services.chat_service import ChatService
        sig = inspect.signature(ChatService.get_user_sessions)
        assert sig.parameters["limit"].default == 50

    def test_get_user_sessions_offset_default_0(self):
        from src.services.chat_service import ChatService
        sig = inspect.signature(ChatService.get_user_sessions)
        assert sig.parameters["offset"].default == 0

    def test_session_title_max_len_constant(self):
        from src.services.chat_service import SESSION_TITLE_MAX_LEN
        assert SESSION_TITLE_MAX_LEN == 60, (
            f"Expected SESSION_TITLE_MAX_LEN=60, got {SESSION_TITLE_MAX_LEN}"
        )


# ===========================================================================
# 3. Title truncation behaviour
# ===========================================================================
class TestSessionTitleTruncation:
    def _make_service(self) -> "ChatService":
        from src.services.chat_service import ChatService
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return ChatService(db)

    def _get_created_session(self, service):
        """Return the ChatSession instance passed to db.add()."""
        return service.db.add.call_args[0][0]

    def test_long_question_truncated_with_ellipsis(self):
        from src.services.chat_service import SESSION_TITLE_MAX_LEN
        svc = self._make_service()
        long_q = "X" * (SESSION_TITLE_MAX_LEN + 50)

        asyncio.run(svc.create_session("user-1", long_q))

        session = self._get_created_session(svc)
        assert session.title.endswith("…"), "Long titles must end with '…'"
        # Length should be MAX_LEN + 1 (for the ellipsis char)
        assert len(session.title) == SESSION_TITLE_MAX_LEN + 1

    def test_short_question_stored_as_is(self):
        svc = self._make_service()
        short_q = "What is the attendance policy?"

        asyncio.run(svc.create_session("user-1", short_q))

        session = self._get_created_session(svc)
        assert session.title == short_q

    def test_exact_max_len_not_truncated(self):
        from src.services.chat_service import SESSION_TITLE_MAX_LEN
        svc = self._make_service()
        exact_q = "A" * SESSION_TITLE_MAX_LEN

        asyncio.run(svc.create_session("user-1", exact_q))

        session = self._get_created_session(svc)
        assert session.title == exact_q, "Exact-length question should NOT be truncated"
        assert not session.title.endswith("…")

    def test_limit_capped_internally(self):
        """get_user_sessions must cap limit at 200 to prevent huge DB queries."""
        src = (BACKEND / "src" / "services" / "chat_service.py").read_text()
        # The capping logic must be present
        assert "min(limit, 200)" in src or "limit = min" in src, (
            "ChatService.get_user_sessions must cap limit at 200"
        )


# ===========================================================================
# 4. Chat route pagination query params
# ===========================================================================
class TestChatRoutePagination:
    def test_get_sessions_has_limit_query_param(self):
        from src.api.routes.chat import get_sessions
        sig = inspect.signature(get_sessions)
        assert "limit" in sig.parameters, "GET /sessions route missing 'limit' query param"

    def test_get_sessions_has_offset_query_param(self):
        from src.api.routes.chat import get_sessions
        sig = inspect.signature(get_sessions)
        assert "offset" in sig.parameters, "GET /sessions route missing 'offset' query param"

    def test_get_sessions_passes_limit_offset_to_service(self):
        """When limit/offset are passed, they flow through to the service call."""
        src = (BACKEND / "src" / "api" / "routes" / "chat.py").read_text()
        assert "limit=limit" in src, "chat route must pass limit= to chat_service"
        assert "offset=offset" in src, "chat route must pass offset= to chat_service"


# ===========================================================================
# 5. No bare print() or traceback.print_exc() in executable code
# ===========================================================================
class TestNoBarePrints:
    def _check_no_print(self, rel_path: str) -> None:
        src = (BACKEND / rel_path).read_text()
        assert not _ast_has_print_call(src), (
            f"{rel_path} contains bare print() calls — use logger instead"
        )

    def test_vector_store_no_print(self):
        self._check_no_print("src/memory/vector_store.py")

    def test_graph_store_no_print(self):
        self._check_no_print("src/memory/graph_store.py")

    def test_ingest_service_no_print(self):
        self._check_no_print("src/services/ingest_service.py")

    def test_document_loader_no_print(self):
        self._check_no_print("src/knowledge/document_loader.py")

    def test_handbook_rag_pipeline_no_print(self):
        self._check_no_print("src/knowledge/handbook_rag_pipeline.py")

    def test_chat_route_no_traceback_print_exc(self):
        src = (BACKEND / "src/api/routes/chat.py").read_text()
        assert not _ast_has_traceback_print_exc(src), (
            "chat.py must not call traceback.print_exc() — use logger.exception()"
        )

    def test_auth_service_no_print(self):
        self._check_no_print("src/services/auth_service.py")
