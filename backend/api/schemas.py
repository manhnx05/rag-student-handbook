from typing import Optional

from pydantic import BaseModel


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
