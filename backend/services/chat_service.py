"""Database operations for chat sessions and messages."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.db.models import ChatMessage, ChatSession

# Maximum characters kept for the auto-generated session title
SESSION_TITLE_MAX_LEN = 60


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def get_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ChatSession]:
        """Return paginated chat sessions, newest first."""
        limit = min(limit, 200)
        result = await self.db.execute(
            select(ChatSession)
            .order_by(desc(ChatSession.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Return a chat session by ID, or None if it does not exist."""
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        return result.scalars().first()

    async def create_session(self, question: str) -> str:
        """Create a new chat session whose title is derived from the first question."""
        session_id = str(uuid.uuid4())
        if len(question) > SESSION_TITLE_MAX_LEN:
            title = question[:SESSION_TITLE_MAX_LEN] + "…"
        else:
            title = question
        new_session = ChatSession(id=session_id, user_id=None, title=title)
        self.db.add(new_session)
        await self.db.commit()
        return session_id

    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and its messages."""
        session = await self.get_session(session_id)
        if not session:
            return False
        await self.db.delete(session)
        await self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def get_session_messages(self, session_id: str) -> Sequence[ChatMessage]:
        """Return all messages for a session in chronological order."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return result.scalars().all()

    async def save_message(
        self, session_id: str, role: str, content: str
    ) -> ChatMessage:
        """Persist a single chat message and bump the session's updated_at."""
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        self.db.add(msg)
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await self.db.flush()
        await self.db.commit()
        return msg
