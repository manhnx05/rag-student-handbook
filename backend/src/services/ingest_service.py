import os
import shutil
import asyncio
from fastapi import UploadFile

from src.knowledge.handbook_rag_pipeline import ingest_pdf

class IngestionService:
    @staticmethod
    def save_upload_file(upload_file: UploadFile, destination_path: str) -> None:
        try:
            with open(destination_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
        finally:
            upload_file.file.close()

    @staticmethod
    async def process_pdf_ingestion(file_path: str, clear_existing: bool = False) -> int:
        """
        Runs the ingest_pdf pipeline in a background thread to prevent blocking
        the async event loop.
        """
        chunks_count = await asyncio.to_thread(ingest_pdf, file_path, clear_existing)
        return chunks_count
