import os
from typing import Any

import pymupdf4llm
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from backend.config import settings
from backend.utils.helpers import get_logger

logger = get_logger(__name__)

HEADERS_TO_SPLIT_ON = [
    ("#", "Header_1"),
    ("##", "Header_2"),
    ("###", "Header_3"),
]


def _page_number(metadata: dict[str, Any]) -> int | None:
    """Return the 1-based page number reported by pymupdf4llm, if available."""
    page = metadata.get("page_number", metadata.get("page"))
    if page is None:
        return None
    try:
        return int(page)
    except (TypeError, ValueError):
        return None


def process_pdf_to_chunks(pdf_path: str) -> list[dict[str, Any]]:
    """
    Reads a PDF student handbook file, converts it to Markdown preserving tables,
    and splits its content into semantic chunks based on Markdown headers.

    Chunk size/overlap come from settings.CHUNK_SIZE / settings.CHUNK_OVERLAP and
    every chunk keeps the source page number so answers can be cited precisely.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at the specified path: {pdf_path}")

    file_name = os.path.basename(pdf_path)
    logger.info("Reading document and converting to Markdown: %s", file_name)

    # page_chunks=True keeps page metadata, which is required for page-level citations.
    page_documents = pymupdf4llm.to_markdown(pdf_path, page_chunks=True)

    logger.info("Applying MarkdownHeaderTextSplitter...")
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )

    # Fallback splitter for sections that are too long
    logger.info(
        "Applying RecursiveCharacterTextSplitter as fallback (size=%d, overlap=%d)",
        settings.CHUNK_SIZE,
        settings.CHUNK_OVERLAP,
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )

    final_chunks: list[dict[str, Any]] = []
    for page_document in page_documents:
        page_text = page_document.get("text", "")
        if not page_text.strip():
            continue

        page_number = _page_number(page_document.get("metadata", {}))
        header_splits = markdown_splitter.split_text(page_text)
        for document in header_splits:
            if page_number is not None:
                document.metadata["page"] = page_number

        for document in text_splitter.split_documents(header_splits):
            document.metadata["source"] = file_name
            final_chunks.append(
                {
                    "id": f"{file_name}_c{len(final_chunks)}",
                    "content": document.page_content,
                    "metadata": document.metadata,
                }
            )

    logger.info("Generated %d structured Markdown chunks.", len(final_chunks))
    return final_chunks
