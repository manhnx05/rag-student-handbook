import os
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request

from src.services.ingest_service import IngestionService
from src.utils.auth_utils import get_current_admin_user
from src.worker import process_pdf_ingestion_task

logger = logging.getLogger(__name__)

router = APIRouter()
from src.api.limiter import limiter




@router.post("/ingest", summary="Ingest a PDF into the knowledge base (admin only)")
@limiter.limit("5/minute")
async def ingest_documents(
    request: Request,
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
        await IngestionService.save_upload_file(file, file_path)
        process_pdf_ingestion_task.delay(file_path)

        return {
            "message": "Document ingestion started in background via Celery",
            "filename": file.filename,
        }
    except Exception as exc:
        logger.exception("Failed to save uploaded file %s", file.filename)
        raise HTTPException(
            status_code=500, detail=f"Error ingesting document: {str(exc)}"
        )
