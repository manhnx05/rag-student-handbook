import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.core.config import settings
from src.memory.embeddings import get_embedding_model, embed_texts, embed_text

class VectorStore:
    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """Creates the Qdrant collection if it doesn't exist."""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # text-embedding-3-small produces 1536 dimensions
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=1536,
                    distance=models.Distance.COSINE
                )
            )

    def add_chunks(self, chunks: list[dict]):
        """
        Adds chunks to the vector store. Each chunk should have:
        - id: str
        - content: str
        - metadata: dict
        """
        if not chunks:
            return
        
        ids = [chunk["id"] for chunk in chunks]
        documents = [chunk["content"] for chunk in chunks]
        metadatas = [chunk.get("metadata", {}) for chunk in chunks]
        
        # We need to embed the text because Qdrant doesn't have an auto-embedding function like Chroma DB in this specific setup
        # Although Qdrant supports FastEmbed, we are using OpenAI embeddings
        embeddings = embed_texts(documents)
        
        points = []
        for i in range(len(chunks)):
            # Qdrant prefers UUIDs or integers. If ids are string UUIDs, pass them directly.
            # Assuming ids are properly formatted UUID strings.
            points.append(
                models.PointStruct(
                    id=ids[i],
                    vector=embeddings[i],
                    payload={
                        "content": documents[i],
                        **metadatas[i]
                    }
                )
            )
            
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print(f"Added {len(chunks)} chunks to vector store.")

    def query(self, query_text: str, top_k: int | None = None) -> dict:
        """
        Queries the vector store for similar chunks.
        """
        if top_k is None:
            top_k = settings.TOP_K_RESULTS
            
        query_vector = embed_text(query_text)
        
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k
        )
        
        # Format the result to match the expected output structure (similar to chromadb's output)
        ids = []
        documents = []
        metadatas = []
        distances = []
        
        for point in search_result:
            ids.append(str(point.id))
            payload = point.payload or {}
            documents.append(payload.get("content", ""))
            
            # extract metadata by removing content
            metadata = {k: v for k, v in payload.items() if k != "content"}
            metadatas.append(metadata)
            distances.append(point.score)
            
        return {
            "ids": [ids],
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [distances]
        }

    def clear_collection(self):
        """
        Clears all data from the collection.
        """
        try:
            self.client.delete_collection(collection_name=self.collection_name)
        except Exception:
            pass
        self._ensure_collection_exists()
        print("Vector store collection cleared.")

    def count(self) -> int:
        """
        Returns the number of chunks in the collection.
        """
        try:
            count_result = self.client.count(collection_name=self.collection_name)
            return count_result.count
        except Exception:
            return 0


# Singleton instance
_vector_store_instance = None

def get_vector_store() -> VectorStore:
    """
    Returns the singleton VectorStore instance.
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
