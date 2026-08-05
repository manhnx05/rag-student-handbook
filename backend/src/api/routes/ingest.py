import os
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import logging

logger = logging.getLogger(__name__)
from src.services.ingest_service import IngestionService

router = APIRouter()

async def background_ingest(file_path: str):
    try:
        chunks_count = await IngestionService.process_pdf_ingestion(file_path, clear_existing=False)
        logger.info(f"Ingestion completed for {file_path}, chunks: {chunks_count}")
    except Exception as e:
        logger.error(f"Error in background ingestion for {file_path}: {e}")

@router.post("/ingest")
async def ingest_documents(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    raw_dir = os.path.join(os.getcwd(), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    file_path = os.path.join(raw_dir, file.filename)
    
    try:
        # Save file synchronously but quickly, or can be done in thread if huge
        IngestionService.save_upload_file(file, file_path)
        background_tasks.add_task(background_ingest, file_path)
        
        return {
            "message": "Document ingestion started in background",
            "filename": file.filename
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")
