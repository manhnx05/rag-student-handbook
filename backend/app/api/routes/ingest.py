import os
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request

from app.core.config import settings
from app.services.ingest_service import IngestionService
from app.utils.auth_utils import get_current_admin_user
from app.worker import process_pdf_ingestion_task

logger = logging.getLogger(__name__)

router = APIRouter()
from app.api.limiter import limiter




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
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    raw_dir = os.path.join(os.getcwd(), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)

    original_filename = Path(file.filename).name
    stored_filename = f"{uuid.uuid4()}.pdf"
    file_path = os.path.join(raw_dir, stored_filename)

    try:
        await IngestionService.save_upload_file(
            file, file_path, max_size=settings.MAX_UPLOAD_SIZE_BYTES
        )
        process_pdf_ingestion_task.delay(file_path)

        return {
            "message": "Document ingestion started in background via Celery",
            "filename": original_filename,
        }
    except ValueError as exc:
        detail = str(exc)
        status_code = 413 if "maximum size" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        logger.exception("Failed to save uploaded file %s", original_filename)
        raise HTTPException(
            status_code=500, detail="Error starting document ingestion"
        ) from exc
