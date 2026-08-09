import os
import fitz  # PyMuPDF
from langchain_experimental.text_splitter import SemanticChunker
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.core.config import settings


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

    print(f"Reading document: {file_name}...")
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
    print(f"Successfully extracted {len(raw_documents)} pages.")

    # Initialize semantic text splitter using Gemini Embeddings
    print("Initializing Semantic Chunker...")
    embeddings = GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL, google_api_key=settings.GEMINI_API_KEY)
    text_splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")

    final_chunks = []
    print("Processing data chunking...")

    for doc in raw_documents:
        split_texts = text_splitter.split_text(doc["text"])

        for idx, chunk_text in enumerate(split_texts):
            final_chunks.append({
                "id": f"{file_name}_p{doc['metadata']['page']}_c{idx}",
                "content": chunk_text,
                "metadata": doc["metadata"]
            })

    print(f"Completed! Generated a total of {len(final_chunks)} chunks.")
    return final_chunks