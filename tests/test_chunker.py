import os
import tempfile
from src.core.chunker import process_pdf_to_chunks
from pypdf import PdfWriter


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
    
    from pypdf import PdfReader
    reader = PdfReader(packet.name)
    page = reader.pages[0]
    writer.add_page(page)
    
    with open(pdf_path, "wb") as f:
        writer.write(f)
    
    return pdf_path, temp_dir


def test_process_pdf_to_chunks():
    pdf_path, temp_dir = create_test_pdf()
    
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
        os.unlink(pdf_path)


if __name__ == "__main__":
    test_process_pdf_to_chunks()
