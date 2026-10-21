"""
IngestionService — thin async wrapper around the synchronous ingest pipeline.
"""
from __future__ import annotations

import asyncio

from fastapi import UploadFile

from backend.ingestion.loader import ingest_pdf
from backend.utils.helpers import get_logger

logger = get_logger(__name__)


class IngestionService:
    @staticmethod
    async def save_upload_file(upload_file: UploadFile, destination_path: str) -> None:
        """Write the uploaded file to disk asynchronously."""
        try:
            content = await upload_file.read()

            def _write():
                with open(destination_path, "wb") as buf:
                    buf.write(content)

            await asyncio.to_thread(_write)
            logger.info("Saved upload to %s", destination_path)
        finally:
            await upload_file.close()

    @staticmethod
    async def process_pdf_ingestion(
        file_path: str, clear_existing: bool = False
    ) -> int:
        """Run the full ingest pipeline asynchronously.

        Returns:
            Number of chunks indexed into Qdrant.
        """
        logger.info(
            "Launching background ingestion for %s (clear_existing=%s)",
            file_path,
            clear_existing,
        )
        chunks_count: int = await ingest_pdf(file_path, clear_existing=clear_existing)

        logger.info(
            "Background ingestion complete for %s — %d chunks indexed",
            file_path,
            chunks_count,
        )
        return chunks_count
