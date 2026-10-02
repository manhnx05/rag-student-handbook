from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.cache import RedisSemanticCache
from langchain_core.globals import set_llm_cache
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.api.routes import chat, health, ingest
from app.config import settings
from app.db.database import setup_db, close_db
from app.utils.logging_config import get_logger
from app.api.exception_handlers import setup_exception_handlers
from app.api.limiter import limiter
from app.rag.chains.rag_chain import close_executor
from app.rag.knowledge_graph.graph_store import get_graph_store
from app.rag.vectorstore.vector_store import get_vector_store
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_db()
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL, google_api_key=settings.GEMINI_API_KEY)
        set_llm_cache(RedisSemanticCache(redis_url=settings.REDIS_URL, embedding=embeddings))
    except Exception:
        logger.exception("Could not initialize Redis semantic cache")
    yield
    await close_db()
    
    try:
        await close_executor()
    except Exception as e:
        logger.error(f"Error closing LangGraph executor: {e}")
        
    try:
        gs = await get_graph_store()
        await gs.close()
    except Exception as e:
        logger.error(f"Error closing GraphStore: {e}")
        
    try:
        vs = await get_vector_store()
        await vs.close()
    except Exception as e:
        logger.error(f"Error closing VectorStore: {e}")


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
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(ingest.router, prefix="/api", tags=["ingest"])
