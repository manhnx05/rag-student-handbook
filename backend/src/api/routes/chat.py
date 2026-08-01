from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List

from src.orchestration.handbook_orchestrator import HandbookOrchestrator
from src.core.db.database import get_db
from src.services.chat_service import ChatService
from src.utils.auth_utils import get_current_user

router = APIRouter()

def get_orchestrator():
    return HandbookOrchestrator()

def get_chat_service(db: AsyncSession = Depends(get_db)):
    return ChatService(db)

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    
class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str

@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    sessions = await chat_service.get_user_sessions(user_id)
    return [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]

@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service)
):
    session = await chat_service.get_session_if_owned(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = await chat_service.get_session_messages(session_id)
    return [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]


async def stream_and_save_response(
    query: str,
    session_id: str,
    chat_service: ChatService,
    orchestrator: HandbookOrchestrator,
    history: List[tuple]
):
    full_response = ""
    async for chunk in orchestrator.process_query_stream(query, session_id, history):
        full_response += chunk
        yield chunk
        
    await chat_service.save_message(session_id, "ai", full_response)

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest, 
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    orchestrator: HandbookOrchestrator = Depends(get_orchestrator)
):
    try:
        session_id = request.session_id
        
        if not session_id:
            session_id = await chat_service.create_session(user_id, request.question)
        else:
            session = await chat_service.get_session_if_owned(session_id, user_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
                
        history = await chat_service.get_session_history(session_id)
        await chat_service.save_message(session_id, "user", request.question)

        return StreamingResponse(
            stream_and_save_response(request.question, session_id, chat_service, orchestrator, history), 
            media_type="text/plain",
            headers={"X-Session-ID": session_id}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
