import os
import tempfile
from src.core.vector_store import VectorStore


def test_vector_store():
    # Use a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    original_path = os.environ.get("CHROMA_DB_PATH")
    os.environ["CHROMA_DB_PATH"] = temp_dir
    
    try:
        # Reset settings to use temp dir
        from importlib import reload
        import src.config
        reload(src.config)
        from src.config import settings
        settings.CHROMA_DB_PATH = temp_dir
        settings.CHROMA_COLLECTION_NAME = "test_collection"
        
        # Reload vector store module
        import src.core.vector_store
        reload(src.core.vector_store)
        from src.core.vector_store import VectorStore, get_vector_store
        
        # Test 1: Create vector store
        vs = VectorStore()
        assert vs.count() == 0, "New collection should be empty"
        
        # Test 2: Add chunks
        test_chunks = [
            {
                "id": "chunk1",
                "content": "This is the first test chunk about programming.",
                "metadata": {"source": "test1.pdf", "page": 1}
            },
            {
                "id": "chunk2",
                "content": "This is the second test chunk about data science.",
                "metadata": {"source": "test2.pdf", "page": 2}
            }
        ]
        vs.add_chunks(test_chunks)
        assert vs.count() == 2, "Should have 2 chunks"
        
        # Test 3: Query
        results = vs.query("programming", top_k=1)
        assert len(results["documents"][0]) == 1, "Should return 1 result"
        assert "programming" in results["documents"][0][0], "Result should contain 'programming'"
        
        # Test 4: Clear collection
        vs.clear_collection()
        assert vs.count() == 0, "Collection should be empty after clearing"
        
        print("test_vector_store passed!")
    finally:
        # Cleanup
        if original_path:
            os.environ["CHROMA_DB_PATH"] = original_path
        else:
            os.environ.pop("CHROMA_DB_PATH", None)
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_vector_store()
