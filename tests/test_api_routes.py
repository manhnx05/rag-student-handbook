from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


class ChatServiceStub:
    def __init__(self) -> None:
        self.sessions = [
            SimpleNamespace(
                id="session-1",
                title="Student handbook",
                created_at=datetime.now(timezone.utc),
            )
        ]
        self.messages = [
            SimpleNamespace(
                id="message-1",
                role="user",
                content="What is the attendance policy?",
                created_at=datetime.now(timezone.utc),
            )
        ]
        self.saved_messages: list[tuple[str, str, str]] = []
        self.create_session = AsyncMock(return_value="new-session")
        self.get_session = AsyncMock(return_value=self.sessions[0])
        self.get_sessions = AsyncMock(return_value=self.sessions)
        self.get_session_messages = AsyncMock(return_value=self.messages)
        self.delete_session = AsyncMock(return_value=True)
        self.save_message = AsyncMock(side_effect=self._save_message)

    async def _save_message(self, session_id: str, role: str, content: str) -> None:
        self.saved_messages.append((session_id, role, content))


class StreamingOrchestratorStub:
    async def process_query_stream(self, query: str, session_id: str):
        yield f"Answer to: {query}"


@pytest.fixture
def client():
    from app.api.main import app
    from app.api.routes import chat

    service = ChatServiceStub()
    app.dependency_overrides[chat.get_chat_service] = lambda: service
    app.dependency_overrides[chat.get_orchestrator] = StreamingOrchestratorStub
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, service
    app.dependency_overrides.clear()


def test_health_check(client):
    test_client, _ = client
    response = test_client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_sessions_are_available_without_authentication(client):
    test_client, service = client
    response = test_client.get("/api/sessions?limit=10&offset=2")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "session-1"
    service.get_sessions.assert_awaited_once_with(limit=10, offset=2)


def test_get_session_messages_returns_messages(client):
    test_client, _ = client
    response = test_client.get("/api/sessions/session-1/messages")
    assert response.status_code == 200
    assert response.json()[0]["role"] == "user"


def test_missing_session_messages_returns_404(client):
    test_client, service = client
    service.get_session.return_value = None
    response = test_client.get("/api/sessions/missing/messages")
    assert response.status_code == 404


def test_chat_creates_session_and_streams_answer(client):
    test_client, service = client
    response = test_client.post(
        "/api/chat",
        json={"question": "What is the attendance policy?"},
    )
    assert response.status_code == 200
    assert response.headers["x-session-id"] == "new-session"
    assert response.text == "Answer to: What is the attendance policy?"
    assert service.saved_messages == [
        ("new-session", "user", "What is the attendance policy?"),
        ("new-session", "ai", "Answer to: What is the attendance policy?"),
    ]


def test_chat_rejects_unknown_existing_session(client):
    test_client, service = client
    service.get_session.return_value = None
    response = test_client.post(
        "/api/chat",
        json={"question": "Question", "session_id": "missing"},
    )
    assert response.status_code == 404


def test_ingest_queues_pdf_without_authentication(client, monkeypatch, tmp_path):
    test_client, _ = client
    from app.api.routes import ingest

    monkeypatch.setattr(ingest.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(
        ingest.IngestionService,
        "save_upload_file",
        AsyncMock(),
    )
    task = SimpleNamespace(id="task-123")
    monkeypatch.setattr(
        ingest.process_pdf_ingestion_task,
        "delay",
        MagicMock(return_value=task),
    )

    response = test_client.post(
        "/api/ingest",
        files={"file": ("handbook.pdf", b"%PDF-test", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "task-123"


def test_ingest_rejects_non_pdf_files(client):
    test_client, _ = client
    response = test_client.post(
        "/api/ingest",
        files={"file": ("handbook.txt", b"text", "text/plain")},
    )
    assert response.status_code == 400
