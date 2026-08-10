import os
import sys
import pathlib
import tempfile

BACKEND = pathlib.Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.knowledge.text_splitter import process_pdf_to_chunks
from pypdf import PdfWriter  # type: ignore
from unittest.mock import patch


def create_test_pdf():
    """Create a simple test PDF file."""
    temp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(temp_dir, "test.pdf")
    
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    packet = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    c = canvas.Canvas(packet.name, pagesize=letter)
    c.drawString(100, 750, "This is a test document.")
    c.drawString(100, 730, "It contains multiple lines of text.")
    c.drawString(100, 710, "Testing chunking functionality.")
    c.save()
    
    from pypdf import PdfReader  # type: ignore
    reader = PdfReader(packet.name)
    page = reader.pages[0]
    writer.add_page(page)
    
    with open(pdf_path, "wb") as f:
        writer.write(f)
    
    return pdf_path, temp_dir


@patch("src.knowledge.text_splitter.GoogleGenerativeAIEmbeddings")
def test_process_pdf_to_chunks(mock_google_embeddings):
    pdf_path, temp_dir = create_test_pdf()
    
    # Configure mock to return dummy vectors for semantic chunking
    mock_instance = mock_google_embeddings.return_value
    mock_instance.embed_documents.return_value = [[0.1, 0.2] for _ in range(10)]
    
    try:
        chunks = process_pdf_to_chunks(pdf_path)
        
        assert len(chunks) > 0, "Should generate at least one chunk"
        
        for chunk in chunks:
            assert "id" in chunk, "Chunk should have 'id' field"
            assert "content" in chunk, "Chunk should have 'content' field"
            assert "metadata" in chunk, "Chunk should have 'metadata' field"
            assert "source" in chunk["metadata"], "Metadata should have 'source'"
            assert "page" in chunk["metadata"], "Metadata should have 'page'"
        
        print("test_process_pdf_to_chunks passed!")
    finally:
        import shutil
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_process_pdf_to_chunks()
