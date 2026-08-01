import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from src.services.ingest_service import IngestionService

router = APIRouter()

@router.post("/ingest")
async def ingest_documents(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    raw_dir = os.path.join(os.getcwd(), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    file_path = os.path.join(raw_dir, file.filename)
    
    try:
        # Save file synchronously but quickly, or can be done in thread if huge
        IngestionService.save_upload_file(file, file_path)
            
        # Run ingestion pipeline asynchronously to not block event loop
        chunks_count = await IngestionService.process_pdf_ingestion(file_path, clear_existing=False)
        
        return {
            "message": "Document ingestion completed successfully",
            "filename": file.filename,
            "chunks_ingested": chunks_count
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")
