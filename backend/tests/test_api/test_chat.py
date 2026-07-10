import pytest
from httpx import AsyncClient, ASGITransport
from src.api.main import app

@pytest.mark.asyncio
async def test_chat_endpoint_streaming():
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
