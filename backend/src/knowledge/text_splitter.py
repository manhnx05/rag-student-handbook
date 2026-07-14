import os
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.core.config import settings


def process_pdf_to_chunks(pdf_path: str):
    """
    Reads a PDF student handbook file and splits its content into smaller token-based chunks.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at the specified path: {pdf_path}")

    # Extract text from PDF along with page number metadata
    from typing import Any
    reader = PdfReader(pdf_path)
    raw_documents: list[dict[str, Any]] = []
    file_name = os.path.basename(pdf_path)

    print(f"Reading document: {file_name}...")
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():  # Skip blank pages
            raw_documents.append({
                "text": text,
                "metadata": {
                    "source": file_name,
                    "page": page_idx + 1
                }
            })
    print(f"Successfully extracted {len(raw_documents)} pages.")

    # Initialize token-based text splitter using gpt-4o tokenizer (cl100k_base)
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name="gpt-4o",
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )

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