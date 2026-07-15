from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Optional
from src.orchestration.handbook_orchestrator import HandbookOrchestrator

router = APIRouter()

def get_orchestrator():
    return HandbookOrchestrator()

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

@router.post("/chat")
async def chat_endpoint(request: ChatRequest, orchestrator: HandbookOrchestrator = Depends(get_orchestrator)):
    try:
        # Returns a stream of text for real-time UI typing effect
        return StreamingResponse(
            orchestrator.process_query_stream(request.question, request.session_id), 
            media_type="text/plain"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

