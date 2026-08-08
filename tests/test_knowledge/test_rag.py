import pytest
import uuid
from unittest.mock import patch, MagicMock
from src.memory.vector_store import VectorStore

@pytest.fixture
def mock_qdrant_client():
    with patch('src.memory.vector_store.QdrantClient') as mock_client:
        mock_instance = mock_client.return_value
        # Setup mock behavior
        mock_count_result = MagicMock()
        mock_count_result.count = 2
        mock_instance.count.return_value = mock_count_result
        
        mock_instance.search.return_value = [
            MagicMock(id=str(uuid.uuid4()), score=0.9, payload={"content": "programming test", "source": "test1.pdf", "page": 1}),
        ]
        yield mock_instance

@patch('src.memory.vector_store.embed_texts')
@patch('src.memory.vector_store.embed_text')
def test_vector_store(mock_embed_text, mock_embed_texts, mock_qdrant_client):
    # Setup embedding mocks
    mock_embed_texts.return_value = [[0.1]*1536, [0.2]*1536]
    mock_embed_text.return_value = [0.1]*1536
    
    vs = VectorStore()
    
    # Test: Collection Initialization
    mock_qdrant_client.get_collection.assert_called_once()
    
    # Test: Add chunks
    test_chunks = [
        {
            "id": str(uuid.uuid4()),
            "content": "This is the first test chunk about programming.",
            "metadata": {"source": "test1.pdf", "page": 1}
        },
        {
            "id": str(uuid.uuid4()),
            "content": "This is the second test chunk about data science.",
            "metadata": {"source": "test2.pdf", "page": 2}
        }
    ]
    vs.add_chunks(test_chunks)
    mock_qdrant_client.upsert.assert_called_once()
    
    # Test: Query
    results = vs.query("programming", top_k=1)
    assert len(results["documents"][0]) == 1, "Should return 1 result"
    assert "programming" in results["documents"][0][0], "Result should contain 'programming'"
    
    # Test: Clear collection
    vs.clear_collection()
    mock_qdrant_client.delete_collection.assert_called_once()
    
    # Test: Count
    assert vs.count() == 2

if __name__ == "__main__":
    pytest.main([__file__])
