from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from langchain_core.globals import set_llm_cache
from langchain_community.cache import RedisSemanticCache
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import redis
from src.api.routes import chat, health, ingest, auth
from src.core.config import settings
from src.db.database import setup_db, close_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_db()
    try:
        print("Initializing Redis Semantic Cache...")
        embeddings = GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL, google_api_key=settings.GEMINI_API_KEY)
        set_llm_cache(RedisSemanticCache(redis_url=settings.REDIS_URL, embedding=embeddings))
    except Exception as e:
        print(f"Failed to initialize Semantic Cache: {e}")
    yield
    await close_db()

app = FastAPI(
    title="Student Handbook RAG API",
    description="API for the Student Handbook AI Assistant with Streaming capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — origins are read from settings.CORS_ORIGINS so they can be
# overridden at deploy time via the CORS_ORIGINS environment variable
# without touching source code (e.g. "http://localhost:3000,https://prod.example.com").
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(ingest.router, prefix="/api", tags=["ingest"])
