import asyncio

from celery import Celery

from backend.config import settings
from backend.services.ingest_service import IngestionService
from backend.utils.helpers import get_logger

logger = get_logger(__name__)

celery_app = Celery(
    "handbook_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="process_pdf_ingestion")
def process_pdf_ingestion_task(file_path: str, clear_existing: bool = False):
    """Celery task to run the ingestion pipeline."""
    logger.info("Starting Celery task for ingestion: %s", file_path)
    try:
        chunks_count = asyncio.run(
            IngestionService.process_pdf_ingestion(file_path, clear_existing)
        )
        return {"status": "success", "chunks_indexed": chunks_count}
    except Exception as e:
        logger.error("Celery ingestion task failed: %s", e)
        raise e
