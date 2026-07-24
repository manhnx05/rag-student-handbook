import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from src.api.main import app
from src.api.routes.chat import get_orchestrator
from src.utils.auth_utils import get_current_user
from src.core.db.database import get_db


# ── Mock helpers ─────────────────────────────────────────────────────────────

class MockOrchestrator:
    async def process_query_stream(
        self,
        query: str,
        session_id: str | None = None,
        history: list = None,
    ):
        yield "Xin chào! "
        yield f"Bạn hỏi về: {query}"


def override_get_orchestrator():
    return MockOrchestrator()


def override_get_current_user():
    """Bypass JWT auth — return a fake user_id."""
    return "test-user-id"


async def override_get_db():
    """Bypass DB — yield a mock session that no-ops all DB calls."""
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None), all=MagicMock(return_value=[])))))
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    yield session


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_endpoint_streaming():
    app.dependency_overrides[get_orchestrator] = override_get_orchestrator
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat",
                json={"question": "Quy chế học vụ"},
            )

            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]

            # Collect streamed body
            text_content = response.text
            assert "Xin chào" in text_content
            assert "Quy chế học vụ" in text_content
    finally:
        app.dependency_overrides.clear()
