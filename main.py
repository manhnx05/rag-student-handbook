"""
Main FastAPI application entrypoint.

Migrated from src/main/python/app/api/main.py
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.exception_handlers import setup_exception_handlers
from backend.api.limiter import limiter
from backend.api.routes import chat_router, health_router, ingest_router
from backend.config import settings
from backend.db.database import close_db, setup_db
from backend.llm.chains.rag_chain import close_executor
from backend.retrieval.graph_store import get_graph_store
from backend.utils.helpers import get_logger
from backend.vectordb.vector_store import get_vector_store

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_db()

    # The full-text index is required by graph retrieval but may not exist yet
    # (e.g. graph ingestion was disabled during the first ingest).
    try:
        graph_store = await get_graph_store()
        await graph_store.create_entity_index()
    except Exception as e:
        logger.warning("Could not ensure Neo4j entityIndex at startup: %s", e)

    yield
    await close_db()

    try:
        await close_executor()
    except Exception as e:
        logger.error("Error closing LangGraph executor: %s", e)

    try:
        gs = await get_graph_store()
        await gs.close()
    except Exception as e:
        logger.error("Error closing GraphStore: %s", e)

    try:
        vs = await get_vector_store()
        await vs.close()
    except Exception as e:
        logger.error("Error closing VectorStore: %s", e)


app = FastAPI(
    title="Student Handbook RAG API",
    description="API for the Student Handbook AI Assistant with Streaming capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

setup_exception_handlers(app)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS origins can be configured for clients that call the API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(health_router, prefix="/api/health", tags=["health"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
