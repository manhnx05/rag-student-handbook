"""
Handbook RAG Pipeline — end-to-end PDF ingestion.

Merges:
  - app/rag/ingestion/handbook_rag_pipeline.py
  - app/rag/ingestion/document_loader.py

Ingest flow for a single PDF:
  1. Parse PDF pages
  2. Semantic-chunk each page with SemanticChunker
  3. Embed all chunks and upsert into Qdrant (vector search)
  4. [Optional] Run LLM-based entity/relationship extraction on every chunk
     and upsert extracted knowledge into Neo4j (graph search)

Step 4 is controlled by settings.GRAPH_INGESTION_ENABLED.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from backend.chunking.chunker import process_pdf_to_chunks
from backend.config import settings
from backend.utils.helpers import get_logger
from backend.vectordb.vector_store import get_vector_store

logger = get_logger(__name__)

# Number of chunks sent to the graph transformer per call.
GRAPH_BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Graph extraction result type (from document_loader.py)
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

    llm = ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        temperature=0,
        google_api_key=SecretStr(settings.GEMINI_API_KEY),
    )
    llm_transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=[
            "Person",
            "Organization",
            "Department",
            "Topic",
            "Rule",
            "Policy",
            "Document",
            "Process",
            "Entity",
        ],
        allowed_relationships=[
            "HAS_POLICY",
            "BELONGS_TO",
            "DEFINES",
            "RELATED_TO",
            "GOVERNS",
            "REQUIRES",
            "IMPLEMENTS",
        ],
    )

    docs = []
    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "").strip()
        chunk_id = chunk.get("id", f"chunk_{i}")
        metadata = chunk.get("metadata", {})

        if not content:
            logger.debug("Skipping empty chunk %s", chunk_id)
            result.chunks_failed += 1
            continue

        context_parts = [
            f"{k.replace('_', ' ')}: {v}"
            for k, v in metadata.items()
            if k.startswith("Header_")
        ]
        if context_parts:
            content = f"[Context: {' | '.join(context_parts)}]\n{content}"

        docs.append(Document(page_content=content, metadata={"source_chunk": chunk_id}))

    if docs:
        logger.debug("Running LLMGraphTransformer on %d documents...", len(docs))
        # Process in batches so a quota/API error on one batch does not discard
        # the entities already extracted from the previous ones.
        for start in range(0, len(docs), GRAPH_BATCH_SIZE):
            batch = docs[start : start + GRAPH_BATCH_SIZE]
            try:
                graph_documents = llm_transformer.convert_to_graph_documents(batch)
                result.chunks_processed += len(batch)

                for g_doc in graph_documents:
                    source_chunk = g_doc.source.metadata.get("source_chunk", "")

                    for node in g_doc.nodes:
                        all_entities.append(
                            {
                                "name": node.id,
                                "type": node.type,
                                "properties": {"source_chunk": source_chunk},
                            }
                        )

                    for rel in g_doc.relationships:
                        all_relationships.append(
                            {
                                "source": rel.source.id,
                                "target": rel.target.id,
                                "source_type": rel.source.type,
                                "target_type": rel.target.type,
                                "type": rel.type,
                                "properties": {"source_chunk": source_chunk},
                            }
                        )

            except Exception as exc:
                logger.warning(
                    "Graph extraction failed for chunks %d-%d: %s",
                    start,
                    start + len(batch) - 1,
                    exc,
                )
                result.chunks_failed += len(batch)

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


# ---------------------------------------------------------------------------
# Ingestion result type (from handbook_rag_pipeline.py)
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    """Summary of a single PDF ingestion run."""

    chunks_indexed: int = 0
    entities_indexed: int = 0
    relationships_indexed: int = 0
    graph_ingestion_enabled: bool = False
    graph_ingestion_skipped: bool = False

    def __str__(self) -> str:
        parts = [f"chunks={self.chunks_indexed}"]
        if self.graph_ingestion_enabled:
            if self.graph_ingestion_skipped:
                parts.append("graph=skipped(error)")
            else:
                parts.append(
                    f"entities={self.entities_indexed} "
                    f"relationships={self.relationships_indexed}"
                )
        else:
            parts.append("graph=disabled")
        return "IngestResult(" + ", ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Primary public function
# ---------------------------------------------------------------------------

async def ingest_pdf(pdf_path: str, clear_existing: bool = False) -> int:
    """
    Full ingestion pipeline for a PDF file.

    Args:
        pdf_path:       Absolute or relative path to the PDF.
        clear_existing: If True, wipe the Qdrant collection before inserting.

    Returns:
        Number of chunks indexed into Qdrant.
    """
    result = await _run_ingest(pdf_path, clear_existing=clear_existing)
    logger.info("Ingestion finished: %s", result)
    return result.chunks_indexed


async def _run_ingest(pdf_path: str, clear_existing: bool = False) -> IngestResult:
    """Internal implementation — returns the full IngestResult."""
    result = IngestResult(graph_ingestion_enabled=settings.GRAPH_INGESTION_ENABLED)

    # ── 1 + 2: Parse PDF → semantic chunks ──────────────────────────────────
    logger.info("Starting ingestion for: %s", pdf_path)
    chunks = await asyncio.to_thread(process_pdf_to_chunks, pdf_path)

    if not chunks:
        logger.warning("No chunks produced from %s — aborting ingestion", pdf_path)
        return result

    # ── 3: Embed + upsert into Qdrant ───────────────────────────────────────
    vector_store = await get_vector_store()
    if clear_existing:
        logger.info("Clearing existing Qdrant collection…")
        await vector_store.clear_collection()

    await vector_store.add_chunks(chunks)
    result.chunks_indexed = len(chunks)
    logger.info("Qdrant: indexed %d chunks", result.chunks_indexed)

    # ── 4: Entity extraction → Neo4j ────────────────────────────────────────
    if not settings.GRAPH_INGESTION_ENABLED:
        logger.info("Graph ingestion disabled — skipping Neo4j step")
        return result

    try:
        await _ingest_graph(chunks, result)
    except Exception as exc:
        logger.error(
            "Graph ingestion failed (Neo4j may be unavailable): %s — "
            "vector index is still intact",
            exc,
        )
        result.graph_ingestion_skipped = True

    return result


async def _ingest_graph(chunks: list[dict], result: IngestResult) -> None:
    """Run entity/relationship extraction and upsert into Neo4j."""
    from backend.retrieval.graph_store import get_graph_store

    logger.info(
        "Starting graph extraction for %d chunks "
        "(this calls the LLM once per chunk)…",
        len(chunks),
    )

    graph_data = await asyncio.to_thread(extract_from_chunks, chunks)

    graph_store = await get_graph_store()

    # Ensure the full-text index exists before inserting (idempotent)
    await graph_store.create_entity_index()

    result.entities_indexed = await graph_store.add_entities(graph_data.entities)
    result.relationships_indexed = await graph_store.add_relationships(
        graph_data.relationships
    )

    logger.info(
        "Neo4j: upserted %d entities, %d relationships",
        result.entities_indexed,
        result.relationships_indexed,
    )


# ---------------------------------------------------------------------------
# Legacy helper — ingest pre-chunked JSON (keeps backward compatibility)
# ---------------------------------------------------------------------------

async def ingest_chunks_from_json(json_path: str, clear_existing: bool = False) -> int:
    """Ingest chunks from a pre-processed JSON file into Qdrant (+ optionally Neo4j).

    Args:
        json_path:      Path to the JSON file produced by process_pdf_to_chunks.
        clear_existing: If True, clear Qdrant collection before inserting.

    Returns:
        Number of chunks indexed.
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as fh:
        chunks = json.load(fh)

    if not chunks:
        logger.warning("JSON file %s contains no chunks", json_path)
        return 0

    vector_store = await get_vector_store()
    if clear_existing:
        await vector_store.clear_collection()

    await vector_store.add_chunks(chunks)
    logger.info("Ingested %d chunks from %s into Qdrant", len(chunks), json_path)

    if settings.GRAPH_INGESTION_ENABLED:
        try:
            result = IngestResult(graph_ingestion_enabled=True)
            await _ingest_graph(chunks, result)
            logger.info(
                "Graph ingestion from JSON complete: %d entities, %d relationships",
                result.entities_indexed,
                result.relationships_indexed,
            )
        except Exception as exc:
            logger.error("Graph ingestion from JSON failed: %s", exc)

    return len(chunks)
