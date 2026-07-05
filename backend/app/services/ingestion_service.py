
from backend.app.core.chunker import process_pdf_to_chunks
from backend.app.core.graph_store import get_graph_store
from backend.app.core.extractor import extract_from_chunks
from backend.app.rag.qdrant_client import get_qdrant_client
from backend.app.rag.embeddings import get_embedding_model
from backend.app.config import settings
from uuid import uuid4
from qdrant_client.http.models import PointStruct

class IngestionService:
    def __init__(self):
        self.qdrant = get_qdrant_client()
        self.embeddings = get_embedding_model()
        self.graph = get_graph_store()
    
    def ingest_pdf(self, pdf_path: str, clear_existing: bool = False):
        chunks = process_pdf_to_chunks(pdf_path)
        
        # Ingest into Qdrant
        points = []
        for chunk in chunks:
            vector = self.embeddings.embed_query(chunk["content"])
            points.append(
                PointStruct(
                    id=str(uuid4()),
                    vector=vector,
                    payload={
                        "content": chunk["content"],
                        "metadata": chunk["metadata"]
                    }
                )
            )
        
        if clear_existing:
            self.qdrant.delete_collection(collection_name=settings.QDRANT_COLLECTION)
            self.qdrant.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
        
        if points:
            self.qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=points
            )
        
        # Ingest into Neo4j
        extraction = extract_from_chunks(chunks)
        self.graph.add_entities(extraction["entities"])
        self.graph.add_relationships(extraction["relationships"])
        
        print(f"Successfully ingested {len(chunks)} chunks")

ingestion_service = IngestionService()
