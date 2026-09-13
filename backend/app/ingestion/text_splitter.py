import os
import fitz  # PyMuPDF
from langchain_experimental.text_splitter import SemanticChunker
from app.core.config import settings
from app.core.logger import get_logger
from app.embedding.embeddings import get_embedding_model

logger = get_logger(__name__)


def process_pdf_to_chunks(pdf_path: str):
    """
    Reads a PDF student handbook file and splits its content into smaller token-based chunks.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at the specified path: {pdf_path}")

    # Extract text from PDF along with page number metadata
    from typing import Any
    raw_documents: list[dict[str, Any]] = []
    file_name = os.path.basename(pdf_path)

    logger.info("Reading document: %s", file_name)
    doc = fitz.open(pdf_path)
    for page_idx, page in enumerate(doc):
        text = page.get_text()
        if text and text.strip():  # Skip blank pages
            raw_documents.append({
                "text": text,
                "metadata": {
                    "source": file_name,
                    "page": page_idx + 1
                }
            })
    doc.close()
    logger.info("Extracted %d pages from %s", len(raw_documents), file_name)

    # Initialize semantic text splitter using Gemini Embeddings
    logger.info("Initializing semantic chunker with %s", settings.EMBEDDING_MODEL)
    embeddings = get_embedding_model()
    text_splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")

    final_chunks = []
    logger.info("Processing semantic chunks for %s", file_name)

    for doc in raw_documents:
        split_texts = text_splitter.split_text(doc["text"])

        for idx, chunk_text in enumerate(split_texts):
            final_chunks.append({
                "id": f"{file_name}_p{doc['metadata']['page']}_c{idx}",
                "content": chunk_text,
                "metadata": doc["metadata"]
            })

    logger.info("Generated %d chunks from %s", len(final_chunks), file_name)
    return final_chunks