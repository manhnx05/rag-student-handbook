from celery import Celery
from app.core.config import settings
from app.services.ingest_service import IngestionService
from app.core.logger import get_logger
from app.db import database
from app.db.models import IngestionJob
from datetime import datetime, timezone
import asyncio

logger = get_logger(__name__)

celery_app = Celery(
    "handbook_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="process_pdf_ingestion")
def process_pdf_ingestion_task(self, file_path: str, job_id: str, clear_existing: bool = False):
    """Celery task to run the ingestion pipeline."""
    logger.info("Starting Celery ingestion task: %s", job_id)

    async def _run() -> int:
        database.setup_db()
        async with database.AsyncSessionLocal() as db:
            job = await db.get(IngestionJob, job_id)
            if job is None:
                raise ValueError(f"Ingestion job not found: {job_id}")

            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()
            try:
                chunks_count = await IngestionService.process_pdf_ingestion(
                    file_path, clear_existing
                )
                job.status = "completed"
                job.chunks_count = chunks_count
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return chunks_count
            except Exception as exc:
                job.status = "failed"
                job.error_message = str(exc)[:4000]
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                raise

    try:
        chunks_count = asyncio.run(_run())
        return {"status": "success", "job_id": job_id, "chunks_indexed": chunks_count}
    except Exception as e:
        logger.error("Celery ingestion task failed for %s: %s", job_id, e)
        raise
