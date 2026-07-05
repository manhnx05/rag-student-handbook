import json
import os
from src.core.chunker import process_pdf_to_chunks
from src.core.vector_store import get_vector_store


def ingest_pdf(pdf_path: str, clear_existing: bool = False) -> int:
    """
    Ingests a PDF file into the vector store.
    
    Args:
        pdf_path: Path to the PDF file
        clear_existing: Whether to clear existing data before ingesting
    
    Returns:
        Number of chunks ingested
    """
    # Process PDF into chunks
    chunks = process_pdf_to_chunks(pdf_path)
    
    if not chunks:
        print("No chunks to ingest.")
        return 0
    
    # Get vector store instance
    vector_store = get_vector_store()
    
    # Clear existing data if requested
    if clear_existing:
        vector_store.clear_collection()
    
    # Add chunks to vector store
    vector_store.add_chunks(chunks)
    
    return len(chunks)


def ingest_chunks_from_json(json_path: str, clear_existing: bool = False) -> int:
    """
    Ingests chunks from a JSON file into the vector store.
    
    Args:
        json_path: Path to the JSON file containing chunks
        clear_existing: Whether to clear existing data before ingesting
    
    Returns:
        Number of chunks ingested
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    if not chunks:
        print("No chunks to ingest.")
        return 0
    
    # Get vector store instance
    vector_store = get_vector_store()
    
    # Clear existing data if requested
    if clear_existing:
        vector_store.clear_collection()
    
    # Add chunks to vector store
    vector_store.add_chunks(chunks)
    
    return len(chunks)
