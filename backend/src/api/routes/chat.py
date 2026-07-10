from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
from typing import AsyncGenerator

router = APIRouter()

class ChatRequest(BaseModel):
    question: str

async def mock_streaming_response(query: str) -> AsyncGenerator[str, None]:
    # Placeholder for the actual orchestrator/agent response stream
    response_text = f"Xin chào, hệ thống đã nhận được câu hỏi của bạn về: **'{query}'**. \n\n*Tính năng kết nối trực tiếp với Agent đang được cập nhật...*"
    words = response_text.split(" ")
    
    for word in words:
        yield f"{word} "
        await asyncio.sleep(0.05)

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Returns a stream of text for real-time UI typing effect
        return StreamingResponse(mock_streaming_response(request.question), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
