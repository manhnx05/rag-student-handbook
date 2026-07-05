import os
import chromadb
from chromadb.utils import embedding_functions
from src.config import settings
from src.core.embedder import get_embedding_model


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.OPENAI_API_KEY,
            model_name=settings.EMBEDDING_MODEL
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=self.embedding_function
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
        metadatas = [chunk["metadata"] for chunk in chunks]
        
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        print(f"Added {len(chunks)} chunks to vector store.")
    
    def query(self, query_text: str, top_k: int = None) -> dict:
        """
        Queries the vector store for similar chunks.
        """
        if top_k is None:
            top_k = settings.TOP_K_RESULTS
        
        results = self.collection.query(
            query_texts=[query_text],
            n_results=top_k
        )
        return results
    
    def clear_collection(self):
        """
        Clears all data from the collection.
        """
        self.client.delete_collection(name=settings.CHROMA_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=self.embedding_function
        )
        print("Vector store collection cleared.")
    
    def count(self) -> int:
        """
        Returns the number of chunks in the collection.
        """
        return self.collection.count()


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
