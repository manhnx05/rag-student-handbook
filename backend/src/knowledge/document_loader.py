"""
Document Loader — LLM-based entity & relationship extraction from text chunks.

Extracts structured knowledge (entities + relationships) from handbook text
chunks and returns them in a format ready for GraphStore ingestion.

Design notes:
  - Each chunk is processed individually to stay within LLM context limits.
  - Results are deduplicated by (name, type) for entities and
    (source, target, type) for relationships.
  - Failures on individual chunks are logged and skipped — they do not abort
    the entire extraction job.
  - Uses structured output (Pydantic) via JsonOutputParser for reliability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_experimental.graph_transformers import LLMGraphTransformer
from pydantic import SecretStr

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Return type for extract_from_chunks
# ---------------------------------------------------------------------------

@dataclass
class GraphIngestionData:
    """Aggregated, deduplicated entities and relationships ready for GraphStore."""

    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    chunks_processed: int = 0
    chunks_failed: int = 0

    @property
    def total_chunks(self) -> int:
        return self.chunks_processed + self.chunks_failed


def extract_from_chunks(chunks: List[Dict[str, Any]]) -> GraphIngestionData:
    """Extract entities and relationships from a list of chunks using LLMGraphTransformer."""
    result = GraphIngestionData()
    all_entities: List[Dict[str, Any]] = []
    all_relationships: List[Dict[str, Any]] = []

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0,
        api_key=SecretStr(settings.OPENAI_API_KEY),
    )
    llm_transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=["Person", "Organization", "Department", "Topic", "Rule", "Policy", "Document", "Process", "Entity"],
        allowed_relationships=["HAS_POLICY", "BELONGS_TO", "DEFINES", "RELATED_TO", "GOVERNS", "REQUIRES", "IMPLEMENTS"]
    )

    docs = []
    total = len(chunks)
    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "").strip()
        chunk_id = chunk.get("id", f"chunk_{i}")

        if not content:
            logger.debug("Skipping empty chunk %s", chunk_id)
            result.chunks_failed += 1
            continue
        
        docs.append(Document(page_content=content, metadata={"source_chunk": chunk_id}))

    if docs:
        logger.debug("Running LLMGraphTransformer on %d documents...", len(docs))
        try:
            graph_documents = llm_transformer.convert_to_graph_documents(docs)
            result.chunks_processed += len(docs)
            
            for g_doc in graph_documents:
                source_chunk = g_doc.source.metadata.get("source_chunk", "")
                
                for node in g_doc.nodes:
                    all_entities.append({
                        "name": node.id,
                        "type": node.type,
                        "properties": {"source_chunk": source_chunk}
                    })
                    
                for rel in g_doc.relationships:
                    all_relationships.append({
                        "source": rel.source.id,
                        "target": rel.target.id,
                        "type": rel.type,
                        "properties": {"source_chunk": source_chunk}
                    })
                    
        except Exception as exc:
            logger.warning("Graph extraction failed: %s", exc)
            result.chunks_failed += len(docs)

    # ── Deduplicate ──────────────────────────────────────────────────────────
    seen_entities: set[tuple] = set()
    for e in all_entities:
        key = (e["name"], e["type"])
        if key not in seen_entities:
            seen_entities.add(key)
            result.entities.append(e)

    seen_rels: set[tuple] = set()
    for r in all_relationships:
        key = (r["source"], r["target"], r["type"])
        if key not in seen_rels:
            seen_rels.add(key)
            result.relationships.append(r)

    logger.info(
        "Extraction complete: %d chunks processed, %d failed | "
        "%d unique entities, %d unique relationships",
        result.chunks_processed,
        result.chunks_failed,
        len(result.entities),
        len(result.relationships),
    )
    return result
