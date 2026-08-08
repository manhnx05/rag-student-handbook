"""
IngestionService — thin async wrapper around the synchronous ingest pipeline.

The PDF parsing, embedding, and (optionally) graph extraction are all CPU/IO
bound and synchronous.  We run them inside asyncio.to_thread() so they do not
block the FastAPI event loop.
"""
from __future__ import annotations

import asyncio
import shutil

from fastapi import UploadFile

from src.core.logger import get_logger
from src.knowledge.handbook_rag_pipeline import ingest_pdf

logger = get_logger(__name__)


class IngestionService:
    @staticmethod
    def save_upload_file(upload_file: UploadFile, destination_path: str) -> None:
        """Write the uploaded file to disk synchronously.

        Closes the upload file handle when done (required by FastAPI).
        """
        try:
            with open(destination_path, "wb") as buf:
                shutil.copyfileobj(upload_file.file, buf)
            logger.info("Saved upload to %s", destination_path)
        finally:
            upload_file.file.close()

    @staticmethod
    async def process_pdf_ingestion(
        file_path: str, clear_existing: bool = False
    ) -> int:
        """Run the full ingest pipeline in a thread to avoid blocking the event loop.

        Returns:
            Number of chunks indexed into Qdrant.
        """
        logger.info(
            "Launching background ingestion for %s (clear_existing=%s)",
            file_path,
            clear_existing,
        )
        chunks_count: int = await asyncio.to_thread(
            ingest_pdf, file_path, clear_existing
        )
        logger.info(
            "Background ingestion complete for %s — %d chunks indexed",
            file_path,
            chunks_count,
        )
        return chunks_count
