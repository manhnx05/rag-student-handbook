import os
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends

from src.services.ingest_service import IngestionService
from src.utils.auth_utils import get_current_admin_user

logger = logging.getLogger(__name__)

router = APIRouter()


async def _background_ingest(file_path: str) -> None:
    """Background task: run the full ingestion pipeline for one PDF."""
    try:
        chunks_count = await IngestionService.process_pdf_ingestion(
            file_path, clear_existing=False
        )
        logger.info("Ingestion completed for %s — %d chunks indexed", file_path, chunks_count)
    except Exception as exc:
        logger.error("Error in background ingestion for %s: %s", file_path, exc)


@router.post("/ingest", summary="Ingest a PDF into the knowledge base (admin only)")
async def ingest_documents(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    # Require a valid JWT AND admin flag — 401/403 otherwise
    _admin_id: str = Depends(get_current_admin_user),
):
    """Upload a PDF file and trigger background ingestion into Qdrant.

    Requires a valid Bearer JWT whose user has **is_admin = true**.
    The ingestion runs asynchronously; the endpoint returns immediately.
    """
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    raw_dir = os.path.join(os.getcwd(), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)

    file_path = os.path.join(raw_dir, file.filename)

    try:
        IngestionService.save_upload_file(file, file_path)
        background_tasks.add_task(_background_ingest, file_path)

        return {
            "message": "Document ingestion started in background",
            "filename": file.filename,
        }
    except Exception as exc:
        logger.exception("Failed to save uploaded file %s", file.filename)
        raise HTTPException(
            status_code=500, detail=f"Error ingesting document: {str(exc)}"
        )
