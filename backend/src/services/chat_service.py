"""
ChatService — database operations for chat sessions and messages.

Changes vs original:
  - get_user_sessions() accepts optional limit/offset for pagination
  - Session title truncation uses a named constant (SESSION_TITLE_MAX_LEN)
  - All ORM calls use the same async session pattern
"""
from __future__ import annotations

import uuid
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models import ChatMessage, ChatSession

# Maximum characters kept for the auto-generated session title
SESSION_TITLE_MAX_LEN = 60


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ChatSession]:
        """Return paginated sessions for a user, newest first.

        Args:
            user_id: Owner's user ID.
            limit:   Maximum sessions to return (default 50, capped at 200).
            offset:  Number of sessions to skip (for cursor-style pagination).
        """
        # Guard against absurdly large limits from callers
        limit = min(limit, 200)
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_session_if_owned(
        self, session_id: str, user_id: str
    ) -> Optional[ChatSession]:
        """Return the session only if it belongs to user_id, else None."""
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def create_session(self, user_id: str, question: str) -> str:
        """Create a new chat session whose title is derived from the first question."""
        session_id = str(uuid.uuid4())
        # Truncate title and append ellipsis if the question is long
        if len(question) > SESSION_TITLE_MAX_LEN:
            title = question[:SESSION_TITLE_MAX_LEN] + "…"
        else:
            title = question
        new_session = ChatSession(id=session_id, user_id=user_id, title=title)
        self.db.add(new_session)
        await self.db.commit()
        return session_id

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a chat session and its messages if it belongs to the user."""
        session = await self.get_session_if_owned(session_id, user_id)
        if not session:
            return False
        
        await self.db.delete(session)
        await self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def get_session_messages(
        self, session_id: str
    ) -> Sequence[ChatMessage]:
        """Return all messages for a session in chronological order."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return result.scalars().all()

    async def get_session_history(
        self, session_id: str
    ) -> List[Tuple[str, str]]:
        """Return (role, content) tuples for use as LLM conversation history."""
        messages = await self.get_session_messages(session_id)
        return [(str(m.role), str(m.content)) for m in messages]

    async def save_message(
        self, session_id: str, role: str, content: str
    ) -> ChatMessage:
        """Persist a single chat message and return the saved instance."""
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        self.db.add(msg)
        await self.db.commit()
        return msg
