import pytest
from httpx import AsyncClient, ASGITransport
from src.api.main import app
from src.api.routes.chat import get_orchestrator

class MockOrchestrator:
    async def process_query_stream(self, query: str, session_id: str | None = None):
        yield "Xin chào! "
        yield f"Bạn hỏi về: {query}"

def override_get_orchestrator():
    return MockOrchestrator()

@pytest.mark.asyncio
async def test_chat_endpoint_streaming():
    app.dependency_overrides[get_orchestrator] = override_get_orchestrator
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/chat", json={"question": "Quy chế học vụ"})
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        
        # Read the streaming response content
        content = b""
        async for chunk in response.aiter_bytes():
            content += chunk
            
        text_content = content.decode("utf-8")
        assert "Quy chế học vụ" in text_content
        assert "Xin chào" in text_content
        
    app.dependency_overrides.clear()
