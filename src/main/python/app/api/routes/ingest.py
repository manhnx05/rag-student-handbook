"""PDF upload endpoint for the local Streamlit application."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.api.limiter import limiter
from app.services.ingest_service import IngestionService
from app.workers.celery_worker import process_pdf_ingestion_task

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ingest", summary="Queue a PDF for handbook indexing")
@limiter.limit("5/minute")
async def ingest_documents(request: Request, file: UploadFile = File(...)):
    """Save an uploaded PDF and queue its indexing in the background."""
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    filename = Path(file.filename).name
    raw_dir = Path.cwd() / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    file_path = raw_dir / f"{uuid.uuid4().hex}_{filename}"

    try:
        await IngestionService.save_upload_file(file, str(file_path))
        task = process_pdf_ingestion_task.delay(str(file_path))
    except Exception as exc:
        logger.exception("Failed to queue uploaded file %s", filename)
        raise HTTPException(
            status_code=500, detail=f"Error queuing document: {exc}"
        ) from exc

    return {
        "message": "Document ingestion started in background",
        "filename": filename,
        "task_id": task.id,
    }
