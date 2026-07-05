from fastapi import APIRouter, HTTPException
from src.api.schemas import (
    QueryRequest, QueryResponse,
    IngestRequest, IngestResponse,
    StatusResponse
)
from src.services.rag_service import get_rag_service
from src.services.pipeline import run_full_pipeline, check_vector_store_status, check_graph_store_status
from src.core.vector_store import get_vector_store
from src.core.graph_store import get_graph_store

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Endpoint to query the RAG system (with optional graph context).
    """
    try:
        rag_service = get_rag_service()
        result = rag_service.query(
            request.question, 
            request.top_k, 
            use_graph=request.use_graph
        )
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(request: IngestRequest):
    """
    Endpoint to ingest a PDF file (with optional graph ingestion).
    """
    try:
        pdf_path = request.pdf_path or "data/raw/handbook.pdf"
        num_ingested = run_full_pipeline(
            pdf_path, 
            clear_existing=request.clear_existing,
            ingest_graph=request.ingest_graph
        )
        return IngestResponse(
            success=True,
            chunks_ingested=num_ingested,
            message=f"Ingested {num_ingested} chunks successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=StatusResponse)
async def status_endpoint():
    """
    Endpoint to check the vector store and graph store status.
    """
    try:
        vector_count = check_vector_store_status()
        try:
            graph_stats = check_graph_store_status()
        except Exception:
            graph_stats = {"node_count": None, "relationship_count": None}
        
        return StatusResponse(
            success=True,
            chunk_count=vector_count,
            node_count=graph_stats.get("node_count"),
            relationship_count=graph_stats.get("relationship_count"),
            message=f"Vector: {vector_count} chunks | Graph: {graph_stats.get('node_count', 0)} nodes, {graph_stats.get('relationship_count', 0)} rels"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear", response_model=StatusResponse)
async def clear_endpoint():
    """
    Endpoint to clear the vector store and graph store.
    """
    try:
        vector_store = get_vector_store()
        vector_store.clear_collection()
        
        try:
            graph_store = get_graph_store()
            graph_store.clear_graph()
        except Exception:
            pass
        
        return StatusResponse(
            success=True,
            chunk_count=0,
            node_count=0,
            relationship_count=0,
            message="Vector and graph stores cleared successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
