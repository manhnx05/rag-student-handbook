from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = None
    use_graph: Optional[bool] = True


class SourceDocument(BaseModel):
    content: str
    metadata: Dict[str, Any]
    distance: float


class GraphNode(BaseModel):
    node: Dict[str, Any]
    score: float
    connections: List[Dict[str, Any]]


class QueryResponse(BaseModel):
    question: str
    answer: str
    vector_sources: List[SourceDocument]
    graph_sources: Optional[List[GraphNode]] = None


class IngestRequest(BaseModel):
    pdf_path: Optional[str] = None
    clear_existing: bool = True
    ingest_graph: Optional[bool] = True


class IngestResponse(BaseModel):
    success: bool
    chunks_ingested: int
    message: str


class StatusResponse(BaseModel):
    success: bool
    chunk_count: int
    node_count: Optional[int] = None
    relationship_count: Optional[int] = None
    message: str
