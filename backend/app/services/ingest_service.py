"""
IngestionService — thin async wrapper around the synchronous ingest pipeline.

The PDF parsing, embedding, and (optionally) graph extraction are all CPU/IO
bound and synchronous.  We run them inside asyncio.to_thread() so they do not
block the FastAPI event loop.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import UploadFile

from app.core.config import settings
from app.core.logger import get_logger
from app.ingestion.handbook_rag_pipeline import ingest_pdf

logger = get_logger(__name__)


class IngestionService:
    @staticmethod
    async def save_upload_file(
        upload_file: UploadFile,
        destination_path: str,
        max_size: int = settings.MAX_UPLOAD_SIZE_BYTES,
    ) -> int:
        """Write the uploaded file to disk asynchronously to avoid blocking the event loop.

        Closes the upload file handle when done (required by FastAPI).
        """
        total_size = 0
        first_chunk = True
        try:
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            output = await asyncio.to_thread(open, destination_path, "wb")
            try:
                while True:
                    content = await upload_file.read(1024 * 1024)
                    if not content:
                        break
                    if first_chunk and not content.startswith(b"%PDF-"):
                        raise ValueError("Uploaded file is not a valid PDF")
                    first_chunk = False
                    total_size += len(content)
                    if total_size > max_size:
                        raise ValueError("Uploaded file exceeds the maximum size")
                    await asyncio.to_thread(output.write, content)
                await asyncio.to_thread(output.close)
            except Exception:
                await asyncio.to_thread(output.close)
                raise

            logger.info("Saved upload to %s (%d bytes)", destination_path, total_size)
            return total_size
        except Exception:
            try:
                os.remove(destination_path)
            except FileNotFoundError:
                pass
            raise
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
