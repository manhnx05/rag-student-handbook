
import redis.asyncio as redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.knowledge_graph.graph_store import get_graph_store
from app.vector_store.vector_store import get_vector_store

router = APIRouter()

@router.get("/")
def health_check():
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Report whether all services required to serve requests are available."""
    checks: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "failed"

    try:
        await get_vector_store()
        checks["qdrant"] = "ok"
    except Exception:
        checks["qdrant"] = "failed"

    try:
        graph_store = await get_graph_store()
        await graph_store.driver.verify_connectivity()
        checks["neo4j"] = "ok"
    except Exception:
        checks["neo4j"] = "failed"

    try:
        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "failed"

    ready = all(status == "ok" for status in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
