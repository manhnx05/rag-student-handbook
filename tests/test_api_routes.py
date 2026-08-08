"""
API Route Integration Tests
============================
Uses FastAPI TestClient (httpx) to test all API endpoints end-to-end
with mocked services. No real DB, Neo4j, Qdrant, or LLM calls are made.

Coverage:
  Auth routes:
    - POST /api/auth/register — success, duplicate email
    - POST /api/auth/login — success, wrong credentials
    - POST /api/auth/google — success, invalid token
    - POST /api/auth/forgot-password — success, google user
    - POST /api/auth/reset-password — success, invalid token

  Chat routes:
    - GET /api/sessions — authenticated, paginated, unauthenticated
    - GET /api/sessions/{id}/messages — owned, not owned
    - POST /api/chat — new session, existing session, session not found

  Ingest routes:
    - POST /api/ingest — admin success, non-admin 403, unauthenticated 401, non-pdf 400

  Health route:
    - GET /api/health/ — always 200
"""
from __future__ import annotations

import io
import os
import pathlib
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

from fastapi.testclient import TestClient
from src.utils.auth_utils import create_access_token


# ---------------------------------------------------------------------------
# App factory — creates a clean FastAPI app with all real routers but
# mocked out external dependencies (Redis cache, DB session, auth)
# ---------------------------------------------------------------------------

def _build_app():
    """Build the FastAPI app with startup lifespan mocked out."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from src.api.routes import auth, chat, health, ingest
    from src.core.config import settings

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(health.router, prefix="/api/health", tags=["health"])
    app.include_router(ingest.router, prefix="/api", tags=["ingest"])
    return app


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _make_token(user_id: str = "user-123", is_admin: bool = False) -> str:
    return create_access_token({"sub": user_id})


def _admin_token(user_id: str = "admin-001") -> str:
    return create_access_token({"sub": user_id})


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_mock_session(session_id: str = None, title: str = "Q") -> MagicMock:
    s = MagicMock()
    s.id = session_id or str(uuid.uuid4())
    s.title = title
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    return s


def _make_mock_message(role: str, content: str) -> MagicMock:
    m = MagicMock()
    m.id = str(uuid.uuid4())
    m.role = role
    m.content = content
    m.created_at = datetime.now(timezone.utc)
    return m


# ===========================================================================
# Health route
# ===========================================================================
class TestHealthRoute:
    def setup_method(self):
        self.app = _build_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_health_returns_200(self):
        resp = self.client.get("/api/health/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


# ===========================================================================
# Auth routes
# ===========================================================================
class TestAuthRoutes:
    def setup_method(self):
        self.app = _build_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _mock_auth_service(self, method: str, return_value=None, side_effect=None):
        """Patch AuthService.<method> for the duration of one request."""
        target = f"src.services.auth_service.AuthService.{method}"
        if side_effect:
            return patch(target, new_callable=AsyncMock, side_effect=side_effect)
        return patch(target, new_callable=AsyncMock, return_value=return_value)

    # register
    def test_register_success_returns_200(self):
        payload = {"access_token": "tok", "token_type": "bearer", "user": {"id": "u1", "email": "a@b.com"}}
        with self._mock_auth_service("register", return_value=payload):
            resp = self.client.post("/api/auth/register", json={"email": "a@b.com", "password": "pw"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_register_duplicate_email_returns_400(self):
        from fastapi import HTTPException
        with self._mock_auth_service("register", side_effect=HTTPException(400, "Email already registered")):
            resp = self.client.post("/api/auth/register", json={"email": "dup@b.com", "password": "pw"})
        assert resp.status_code == 400

    def test_register_missing_fields_returns_422(self):
        resp = self.client.post("/api/auth/register", json={"email": "a@b.com"})  # missing password
        assert resp.status_code == 422

    # login
    def test_login_success_returns_200(self):
        payload = {"access_token": "tok", "token_type": "bearer", "user": {"id": "u1", "email": "a@b.com"}}
        with self._mock_auth_service("login", return_value=payload):
            resp = self.client.post("/api/auth/login", json={"email": "a@b.com", "password": "pw"})
        assert resp.status_code == 200

    def test_login_wrong_credentials_returns_400(self):
        from fastapi import HTTPException
        with self._mock_auth_service("login", side_effect=HTTPException(400, "Incorrect email or password")):
            resp = self.client.post("/api/auth/login", json={"email": "x@b.com", "password": "wrong"})
        assert resp.status_code == 400

    # google
    def test_google_auth_success_returns_200(self):
        payload = {"access_token": "tok", "token_type": "bearer", "user": {"id": "g1", "email": "g@gmail.com"}}
        with self._mock_auth_service("google_auth", return_value=payload):
            resp = self.client.post("/api/auth/google", json={"credential": "google-id-token"})
        assert resp.status_code == 200

    def test_google_auth_invalid_token_returns_400(self):
        from fastapi import HTTPException
        with self._mock_auth_service("google_auth", side_effect=HTTPException(400, "Invalid Google token")):
            resp = self.client.post("/api/auth/google", json={"credential": "bad-token"})
        assert resp.status_code == 400

    # forgot password
    def test_forgot_password_returns_200_always(self):
        payload = {"message": "If that email is in our database..."}
        with self._mock_auth_service("forgot_password", return_value=payload):
            resp = self.client.post("/api/auth/forgot-password", json={"email": "any@example.com"})
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_forgot_password_google_user_returns_400(self):
        from fastapi import HTTPException
        with self._mock_auth_service("forgot_password", side_effect=HTTPException(400, "Google Login")):
            resp = self.client.post("/api/auth/forgot-password", json={"email": "g@gmail.com"})
        assert resp.status_code == 400

    # reset password
    def test_reset_password_success(self):
        with self._mock_auth_service("reset_password", return_value={"message": "Password updated successfully"}):
            resp = self.client.post("/api/auth/reset-password", json={"token": "tok", "new_password": "newpw"})
        assert resp.status_code == 200

    def test_reset_password_invalid_token_returns_400(self):
        from fastapi import HTTPException
        with self._mock_auth_service("reset_password", side_effect=HTTPException(400, "Invalid or expired reset token")):
            resp = self.client.post("/api/auth/reset-password", json={"token": "bad", "new_password": "pw"})
        assert resp.status_code == 400


# ===========================================================================
# Chat routes
# ===========================================================================
class TestChatRoutes:
    def setup_method(self):
        self.app = _build_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.token = _make_token("user-123")
        self.headers = _auth_headers(self.token)

    def _override_get_current_user(self, user_id: str = "user-123"):
        from src.utils.auth_utils import get_current_user
        self.app.dependency_overrides[get_current_user] = lambda: user_id

    def _override_chat_service(self, mock_svc):
        from src.api.routes.chat import get_chat_service
        self.app.dependency_overrides[get_chat_service] = lambda: mock_svc

    def _clear_overrides(self):
        self.app.dependency_overrides.clear()

    # GET /sessions
    def test_get_sessions_unauthenticated_returns_401(self):
        resp = self.client.get("/api/sessions")
        assert resp.status_code == 401

    def test_get_sessions_authenticated_returns_200(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        session = _make_mock_session(title="Test Session")
        mock_svc.get_user_sessions = AsyncMock(return_value=[session])
        self._override_chat_service(mock_svc)

        resp = self.client.get("/api/sessions", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Test Session"
        self._clear_overrides()

    def test_get_sessions_pagination_params_passed_to_service(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        mock_svc.get_user_sessions = AsyncMock(return_value=[])
        self._override_chat_service(mock_svc)

        self.client.get("/api/sessions?limit=10&offset=20", headers=self.headers)
        mock_svc.get_user_sessions.assert_awaited_once_with("user-123", limit=10, offset=20)
        self._clear_overrides()

    def test_get_sessions_invalid_limit_returns_422(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        mock_svc.get_user_sessions = AsyncMock(return_value=[])
        self._override_chat_service(mock_svc)

        # limit=0 violates ge=1 constraint
        resp = self.client.get("/api/sessions?limit=0", headers=self.headers)
        assert resp.status_code == 422
        self._clear_overrides()

    def test_get_sessions_limit_exceeds_max_returns_422(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        mock_svc.get_user_sessions = AsyncMock(return_value=[])
        self._override_chat_service(mock_svc)

        # limit=201 violates le=200
        resp = self.client.get("/api/sessions?limit=201", headers=self.headers)
        assert resp.status_code == 422
        self._clear_overrides()

    # GET /sessions/{id}/messages
    def test_get_messages_returns_404_for_unowned_session(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        mock_svc.get_session_if_owned = AsyncMock(return_value=None)
        self._override_chat_service(mock_svc)

        resp = self.client.get("/api/sessions/unknown-id/messages", headers=self.headers)
        assert resp.status_code == 404
        self._clear_overrides()

    def test_get_messages_returns_messages_for_owned_session(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        session = _make_mock_session(session_id="sess-1")
        msgs = [
            _make_mock_message("user", "Hello"),
            _make_mock_message("ai", "Hi there"),
        ]
        mock_svc.get_session_if_owned = AsyncMock(return_value=session)
        mock_svc.get_session_messages = AsyncMock(return_value=msgs)
        self._override_chat_service(mock_svc)

        resp = self.client.get("/api/sessions/sess-1/messages", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "ai"
        self._clear_overrides()

    # POST /chat
    def test_chat_unauthenticated_returns_401(self):
        resp = self.client.post("/api/chat", json={"question": "Hello"})
        assert resp.status_code == 401

    def test_chat_creates_new_session_when_no_session_id(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        mock_svc.create_session = AsyncMock(return_value="new-session-id")
        mock_svc.get_session_history = AsyncMock(return_value=[])
        mock_svc.save_message = AsyncMock()

        from src.api.routes.chat import get_orchestrator
        mock_orch = MagicMock()

        async def fake_stream(*args, **kwargs):
            yield "Hello "
            yield "world"

        mock_orch.process_query_stream = fake_stream
        self._override_chat_service(mock_svc)
        self.app.dependency_overrides[get_orchestrator] = lambda: mock_orch

        resp = self.client.post("/api/chat", json={"question": "What is attendance?"}, headers=self.headers)
        assert resp.status_code == 200
        assert resp.headers.get("x-session-id") == "new-session-id"
        mock_svc.create_session.assert_awaited_once()
        self._clear_overrides()

    def test_chat_with_existing_session_id(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        session = _make_mock_session(session_id="existing-sess")
        mock_svc.get_session_if_owned = AsyncMock(return_value=session)
        mock_svc.get_session_history = AsyncMock(return_value=[])
        mock_svc.save_message = AsyncMock()

        from src.api.routes.chat import get_orchestrator
        mock_orch = MagicMock()

        async def fake_stream(*args, **kwargs):
            yield "Answer"

        mock_orch.process_query_stream = fake_stream
        self._override_chat_service(mock_svc)
        self.app.dependency_overrides[get_orchestrator] = lambda: mock_orch

        resp = self.client.post(
            "/api/chat",
            json={"question": "Hello", "session_id": "existing-sess"},
            headers=self.headers,
        )
        assert resp.status_code == 200
        assert resp.headers.get("x-session-id") == "existing-sess"
        mock_svc.create_session.assert_not_awaited()
        self._clear_overrides()

    def test_chat_returns_404_for_unowned_session(self):
        self._override_get_current_user()
        mock_svc = AsyncMock()
        mock_svc.get_session_if_owned = AsyncMock(return_value=None)
        self._override_chat_service(mock_svc)

        resp = self.client.post(
            "/api/chat",
            json={"question": "Hello", "session_id": "not-mine"},
            headers=self.headers,
        )
        assert resp.status_code == 404
        self._clear_overrides()

    def test_chat_missing_question_returns_422(self):
        self._override_get_current_user()
        resp = self.client.post("/api/chat", json={}, headers=self.headers)
        assert resp.status_code == 422
        self._clear_overrides()


# ===========================================================================
# Ingest routes
# ===========================================================================
class TestIngestRoutes:
    def setup_method(self):
        self.app = _build_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _make_pdf_upload(self, filename: str = "handbook.pdf") -> dict:
        return {"file": (filename, io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}

    def _override_admin_user(self, user_id: str = "admin-001"):
        from src.utils.auth_utils import get_current_admin_user
        self.app.dependency_overrides[get_current_admin_user] = lambda: user_id

    def _clear_overrides(self):
        self.app.dependency_overrides.clear()

    def test_ingest_unauthenticated_returns_401(self):
        resp = self.client.post("/api/ingest", files=self._make_pdf_upload())
        # Without token, OAuth2PasswordBearer returns 401
        assert resp.status_code == 401

    def test_ingest_non_admin_returns_403(self):
        """A valid JWT but is_admin=False should get 403."""
        # Override get_current_admin_user to raise 403
        from fastapi import HTTPException
        from src.utils.auth_utils import get_current_admin_user

        def deny():
            raise HTTPException(status_code=403, detail="Admin access required")

        self.app.dependency_overrides[get_current_admin_user] = deny

        token = _make_token("normal-user")
        resp = self.client.post(
            "/api/ingest",
            files=self._make_pdf_upload(),
            headers=_auth_headers(token),
        )
        assert resp.status_code == 403
        self._clear_overrides()

    def test_ingest_non_pdf_returns_400(self):
        self._override_admin_user()

        resp = self.client.post(
            "/api/ingest",
            files={"file": ("document.docx", io.BytesIO(b"fake"), "application/octet-stream")},
            headers=_auth_headers(_admin_token()),
        )
        assert resp.status_code == 400
        assert "pdf" in resp.json()["detail"].lower()
        self._clear_overrides()

    def test_ingest_valid_pdf_triggers_background_task(self):
        self._override_admin_user()

        with (
            patch("src.api.routes.ingest.IngestionService.save_upload_file"),
            patch("src.api.routes.ingest.process_pdf_ingestion_task.delay"),
        ):
            resp = self.client.post(
                "/api/ingest",
                files=self._make_pdf_upload("handbook.pdf"),
                headers=_auth_headers(_admin_token()),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "handbook.pdf"
        assert "celery" in data["message"].lower()
        self._clear_overrides()

    def test_ingest_file_save_error_returns_500(self):
        self._override_admin_user()

        with patch(
            "src.api.routes.ingest.IngestionService.save_upload_file",
            side_effect=OSError("disk full"),
        ):
            resp = self.client.post(
                "/api/ingest",
                files=self._make_pdf_upload(),
                headers=_auth_headers(_admin_token()),
            )

        assert resp.status_code == 500
        self._clear_overrides()
