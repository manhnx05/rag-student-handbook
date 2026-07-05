
from fastapi import APIRouter, UploadFile, File
from typing import Optional
from backend.app.services.ingestion_service import ingestion_service

router = APIRouter()

@router.post("/pdf")
def ingest_pdf(file: UploadFile = File(...), clear_existing: bool = False):
    # Save uploaded file
    import os
    upload_dir = "data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_location = os.path.join(upload_dir, file.filename)
    
    with open(file_location, "wb+") as file_object:
        file_object.write(file.file.read())
    
    # Ingest
    ingestion_service.ingest_pdf(file_location, clear_existing)
    
    return {"status": "success", "file": file.filename}
