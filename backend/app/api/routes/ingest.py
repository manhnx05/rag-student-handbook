import os
import logging
import uuid
import hashlib
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.database import get_db
from app.db.models import Document, IngestionJob
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
    db: AsyncSession = Depends(get_db),
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
        content_hash = await _sha256_file(file_path)
        existing = await db.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        if existing.scalars().first():
            os.remove(file_path)
            raise HTTPException(status_code=409, detail="Document already ingested")

        document = Document(
            filename=original_filename,
            content_hash=content_hash,
            created_by=_admin_id,
        )
        db.add(document)
        await db.flush()

        job = IngestionJob(document_id=document.id, created_by=_admin_id)
        db.add(job)
        await db.commit()
        await db.refresh(job)

        task = process_pdf_ingestion_task.delay(file_path, job.id)
        job.celery_task_id = task.id
        await db.commit()

        return {
            "message": "Document ingestion started in background via Celery",
            "filename": original_filename,
            "job_id": job.id,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        detail = str(exc)
        status_code = 413 if "maximum size" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        logger.exception("Failed to save uploaded file %s", original_filename)
        raise HTTPException(
            status_code=500, detail="Error starting document ingestion"
        ) from exc


@router.get("/ingest/jobs/{job_id}", summary="Get an ingestion job status")
async def get_ingestion_job(
    job_id: str,
    _admin_id: str = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(IngestionJob, job_id)
    if job is None or job.created_by != _admin_id:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    return {
        "id": job.id,
        "document_id": job.document_id,
        "status": job.status,
        "chunks_count": job.chunks_count,
        "entities_count": job.entities_count,
        "relationships_count": job.relationships_count,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


async def _sha256_file(file_path: str) -> str:
    digest = hashlib.sha256()

    def _read_chunks() -> None:
        with open(file_path, "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)

    import asyncio

    await asyncio.to_thread(_read_chunks)
    return digest.hexdigest()
