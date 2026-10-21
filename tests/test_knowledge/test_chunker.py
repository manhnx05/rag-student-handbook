"""Tests for the Markdown-based chunker (backend.chunking.chunker)."""

from unittest.mock import patch

import pytest

from backend.chunking.chunker import process_pdf_to_chunks


def test_process_pdf_to_chunks_uses_page_markdown(tmp_path):
    """process_pdf_to_chunks reads page-chunked Markdown and keeps citations."""
    pdf_path = tmp_path / "handbook.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")
    pages = [
        {
            "metadata": {"page": 1},
            "text": "# Học phí\nSinh viên đóng học phí theo số tín chỉ đã đăng ký.",
        },
        {
            "metadata": {"page": 2},
            "text": "## Đăng ký học phần\nSinh viên đăng ký học phần trên cổng thông tin.",
        },
    ]

    with patch(
        "backend.chunking.chunker.pymupdf4llm.to_markdown",
        return_value=pages,
    ) as to_markdown:
        chunks = process_pdf_to_chunks(str(pdf_path))

    to_markdown.assert_called_once_with(str(pdf_path), page_chunks=True)
    assert len(chunks) > 0, "Should generate at least one chunk"

    for index, chunk in enumerate(chunks):
        assert chunk["id"] == f"handbook.pdf_c{index}"
        assert "content" in chunk
        assert "metadata" in chunk
        assert chunk["metadata"]["source"] == "handbook.pdf"
        assert "page" in chunk["metadata"]

    assert {chunk["metadata"]["page"] for chunk in chunks} == {1, 2}


def test_process_pdf_to_chunks_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        process_pdf_to_chunks(str(tmp_path / "does_not_exist.pdf"))
