"""
Merged API routes — combines chat, health, and ingest endpoints.

Merges:
  - app/api/routes/chat.py
  - app/api/routes/health.py
  - app/api/routes/ingest.py
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.limiter import limiter
from backend.api.schemas import ChatRequest, MessageResponse, SessionResponse
from backend.db.database import get_db
from backend.services.chat_service import ChatService
from backend.services.handbook_orchestrator import HandbookOrchestrator
from backend.services.ingest_service import IngestionService
from backend.utils.helpers import HandbookException
from backend.workers.celery_worker import process_pdf_ingestion_task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------

chat_router = APIRouter()


@lru_cache()
def get_orchestrator() -> HandbookOrchestrator:
    """Single HandbookOrchestrator per worker process (lru_cache = singleton)."""
    return HandbookOrchestrator()


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


@chat_router.get("/sessions", response_model=List[SessionResponse])
@limiter.limit("20/minute")
async def get_sessions(
    request: Request,
    chat_service: ChatService = Depends(get_chat_service),
    limit: int = Query(default=50, ge=1, le=200, description="Max sessions to return"),
    offset: int = Query(default=0, ge=0, description="Sessions to skip (pagination)"),
):
    """Return paginated chat sessions, newest first."""
    sessions = await chat_service.get_sessions(limit=limit, offset=offset)
    return [
        {"id": s.id, "title": s.title, "created_at": s.created_at.isoformat()}
        for s in sessions
    ]


@chat_router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Return all messages for a session."""
    session = await chat_service.get_session(session_id)
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


@chat_router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Delete a chat session and all its messages."""
    success = await chat_service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return None


async def _stream_and_save(
    stream: AsyncIterator[str],
    session_id: str,
    chat_service: ChatService,
):
    """Async generator: stream AI response chunks and persist the full reply."""
    full_response = ""
    try:
        async for chunk in stream:
            full_response += chunk
            yield chunk
    finally:
        if full_response.strip():
            await chat_service.save_message(session_id, "ai", full_response)


@chat_router.post("/chat")
@limiter.limit("10/minute")
async def chat_endpoint(
    request: Request,
    chat_request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
    orchestrator: HandbookOrchestrator = Depends(get_orchestrator),
):
    """Stream an AI response for the user's question."""
    try:
        session_id = chat_request.session_id

        if not session_id:
            session_id = await chat_service.create_session(chat_request.question)
        else:
            session = await chat_service.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

        # Build the stream before returning the response: guardrail rejections must
        # surface as an error status, not as an already-started 200 stream.
        stream = orchestrator.process_query_stream(chat_request.question, session_id)

        await chat_service.save_message(session_id, "user", chat_request.question)

        return StreamingResponse(
            _stream_and_save(stream, session_id, chat_service),
            media_type="text/plain",
            headers={"X-Session-ID": session_id},
        )
    except HTTPException:
        raise
    except HandbookException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error in chat endpoint: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Health route
# ---------------------------------------------------------------------------

health_router = APIRouter()


@health_router.get("/")
def health_check():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Ingest route
# ---------------------------------------------------------------------------

ingest_router = APIRouter()


@ingest_router.post("/ingest", summary="Queue a PDF for handbook indexing")
@limiter.limit("5/minute")
async def ingest_documents(request: Request, file: UploadFile = File(...)):
    """Save an uploaded PDF and queue its indexing in the background."""
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    filename = Path(file.filename).name
    raw_dir = Path.cwd() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    file_path = raw_dir / f"{uuid.uuid4().hex}_{filename}"

    try:
        await IngestionService.save_upload_file(file, str(file_path))
        task = process_pdf_ingestion_task.delay(str(file_path))
    except Exception as exc:
        logger.exception("Failed to queue uploaded file %s", filename)
        raise HTTPException(
            status_code=500, detail=f"Error queuing document: {exc}"
        ) from exc

    return {
        "message": "Document ingestion started in background",
        "filename": filename,
        "task_id": task.id,
    }
