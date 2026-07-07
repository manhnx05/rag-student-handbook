
from fastapi import APIRouter
from pydantic import BaseModel
from backend.app.services.chat_service import chat_service

router = APIRouter()

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    sources: list = []

@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest):
    response = chat_service.query(request.question)
    return ChatResponse(answer=response["answer"], sources=response["sources"])
