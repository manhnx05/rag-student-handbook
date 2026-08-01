import uuid
from typing import List, Tuple, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from src.core.db.models import ChatSession, ChatMessage


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_sessions(self, user_id: str) -> Sequence[ChatSession]:
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at))
        )
        return result.scalars().all()

    async def get_session_if_owned(self, session_id: str, user_id: str) -> ChatSession | None:
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            )
        )
        return result.scalars().first()

    async def get_session_messages(self, session_id: str) -> Sequence[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return result.scalars().all()

    async def get_session_history(self, session_id: str) -> List[Tuple[str, str]]:
        messages = await self.get_session_messages(session_id)
        return [(str(m.role), str(m.content)) for m in messages]

    async def create_session(self, user_id: str, question: str) -> str:
        session_id = str(uuid.uuid4())
        title = question[:30] + "..." if len(question) > 30 else question
        new_session = ChatSession(id=session_id, user_id=user_id, title=title)
        self.db.add(new_session)
        await self.db.commit()
        return session_id

    async def save_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        self.db.add(msg)
        await self.db.commit()
        return msg
