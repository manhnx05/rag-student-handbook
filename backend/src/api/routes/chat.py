"""
Chat API routes — sessions, messages, and streaming chat endpoint.

Changes vs original:
  - GET /sessions accepts limit/offset query params (pagination)
  - Exception handler uses logger instead of bare traceback.print_exc()
  - Imports cleaned up
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.database import get_db
from src.orchestration.handbook_orchestrator import HandbookOrchestrator
from src.services.chat_service import ChatService
from src.utils.auth_utils import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

@lru_cache()
def get_orchestrator() -> HandbookOrchestrator:
    """Single HandbookOrchestrator per worker process (lru_cache = singleton)."""
    return HandbookOrchestrator()


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    limit: int = Query(default=50, ge=1, le=200, description="Max sessions to return"),
    offset: int = Query(default=0, ge=0, description="Sessions to skip (pagination)"),
):
    """Return paginated list of the current user's chat sessions, newest first."""
    sessions = await chat_service.get_user_sessions(user_id, limit=limit, offset=offset)
    return [
        {"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()}
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Return all messages for a session owned by the current user."""
    session = await chat_service.get_session_if_owned(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await chat_service.get_session_messages(session_id)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


async def _stream_and_save(
    query: str,
    session_id: str,
    chat_service: ChatService,
    orchestrator: HandbookOrchestrator,
    history: List[tuple],
):
    """Async generator: stream AI response chunks and persist the full reply."""
    full_response = ""
    async for chunk in orchestrator.process_query_stream(query, session_id, history):
        full_response += chunk
        yield chunk

    # Persist the complete response after the stream finishes
    await chat_service.save_message(session_id, "ai", full_response)


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
    orchestrator: HandbookOrchestrator = Depends(get_orchestrator),
):
    """Stream an AI response for the user's question.

    Creates a new session if session_id is omitted.  Returns the session ID
    in the X-Session-ID response header.
    """
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
            _stream_and_save(
                request.question, session_id, chat_service, orchestrator, history
            ),
            media_type="text/plain",
            headers={"X-Session-ID": session_id},
        )
    except HTTPException:
        raise  # re-raise 4xx without logging as server error
    except Exception as exc:
        logger.exception("Unhandled error in chat endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
