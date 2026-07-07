
from fastapi import APIRouter
from backend.app.api import chat, ingest, health

api_router = APIRouter()
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
