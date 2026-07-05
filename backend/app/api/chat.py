
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.app.services.chat_service import chat_service

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    patient_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: list = []

@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    response = chat_service.query(request.question, request.patient_id)
    return ChatResponse(answer=response["answer"], sources=response["sources"])
