
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, SearchRequest
from backend.app.config import settings
from backend.app.rag.embeddings import get_embedding_model
from backend.app.rag.qdrant_client import get_qdrant_client

def hybrid_retrieve(query: str, top_k: int = None, filter: Filter = None):
    if top_k is None:
        top_k = settings.TOP_K_RESULTS
    
    embeddings = get_embedding_model()
    qdrant = get_qdrant_client()
    
    query_vector = embeddings.embed_query(query)
    
    search_result = qdrant.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        limit=top_k,
        query_filter=filter
    )
    
    return search_result
