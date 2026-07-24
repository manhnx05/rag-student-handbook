from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from pydantic import BaseModel
from typing import Optional, List
import uuid

from src.orchestration.handbook_orchestrator import HandbookOrchestrator
from src.core.db.database import get_db
from src.core.db.models import ChatSession, ChatMessage
from src.utils.auth_utils import get_current_user

router = APIRouter()

def get_orchestrator():
    return HandbookOrchestrator()

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
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(desc(ChatSession.updated_at))
    )
    sessions = result.scalars().all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]

@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify session belongs to user
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = msg_result.scalars().all()
    return [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]


async def stream_and_save_response(
    query: str,
    session_id: str,
    db: AsyncSession,
    orchestrator: HandbookOrchestrator,
    history: List[tuple]
):
    # Pass history to orchestrator if supported
    full_response = ""
    # We pass history by updating process_query_stream to accept it.
    async for chunk in orchestrator.process_query_stream(query, session_id, history):
        full_response += chunk
        yield chunk
        
    # After stream is complete, save AI response to DB
    ai_msg = ChatMessage(session_id=session_id, role="ai", content=full_response)
    db.add(ai_msg)
    await db.commit()

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest, 
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    orchestrator: HandbookOrchestrator = Depends(get_orchestrator)
):
    try:
        session_id = request.session_id
        
        # 1. Create session if not exists
        if not session_id:
            session_id = str(uuid.uuid4())
            # Use first 30 chars of question as title
            title = request.question[:30] + "..." if len(request.question) > 30 else request.question
            new_session = ChatSession(id=session_id, user_id=user_id, title=title)
            db.add(new_session)
            await db.commit()
            
        else:
            # Verify session belongs to user
            result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id))
            if not result.scalars().first():
                raise HTTPException(status_code=404, detail="Session not found")
                
        # 2. Fetch history for the session
        msg_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = msg_result.scalars().all()
        history = [(m.role, m.content) for m in messages]
        
        # 3. Save User Message
        user_msg = ChatMessage(session_id=session_id, role="user", content=request.question)
        db.add(user_msg)
        await db.commit()

        # 4. Stream response and save AI message
        # We need to yield a JSON line or custom format if we want to return session_id to frontend on first message.
        # But for simplicity, we will stream text and use headers to return new session_id.
        return StreamingResponse(
            stream_and_save_response(request.question, session_id, db, orchestrator, history), 
            media_type="text/plain",
            headers={"X-Session-ID": session_id}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
