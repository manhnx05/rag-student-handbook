
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from backend.app.config import settings

def get_qdrant_client():
    client = QdrantClient(url=settings.QDRANT_URL)
    
    # Create collection if it doesn't exist
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if settings.QDRANT_COLLECTION not in collection_names:
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    
    return client
