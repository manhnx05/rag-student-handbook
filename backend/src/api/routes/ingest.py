import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from src.knowledge.handbook_rag_pipeline import ingest_pdf

router = APIRouter()

@router.post("/ingest")
async def ingest_documents(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    # Ensure data/raw directory exists
    raw_dir = os.path.join(os.getcwd(), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    file_path = os.path.join(raw_dir, file.filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Run ingestion pipeline
        chunks_count = ingest_pdf(file_path, clear_existing=False)
        
        return {
            "message": "Document ingestion completed successfully",
            "filename": file.filename,
            "chunks_ingested": chunks_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")
    finally:
        file.file.close()
