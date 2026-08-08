"""
Handbook RAG Pipeline — end-to-end PDF ingestion.

Ingest flow for a single PDF:
  1. Parse PDF pages with pypdf
  2. Semantic-chunk each page with SemanticChunker (OpenAI embeddings)
  3. Embed all chunks and upsert into Qdrant (vector search)
  4. [Optional] Run LLM-based entity/relationship extraction on every chunk
     and upsert extracted knowledge into Neo4j (graph search)

Step 4 is controlled by settings.GRAPH_INGESTION_ENABLED.  Set it to False
to skip Neo4j when it is unavailable or during quick iteration cycles.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from src.core.config import settings
from src.core.logger import get_logger
from src.knowledge.document_loader import extract_from_chunks
from src.knowledge.text_splitter import process_pdf_to_chunks
from src.memory.vector_store import get_vector_store

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    """Summary of a single PDF ingestion run."""

    chunks_indexed: int = 0          # chunks pushed to Qdrant
    entities_indexed: int = 0        # entities upserted into Neo4j
    relationships_indexed: int = 0   # relationships upserted into Neo4j
    graph_ingestion_enabled: bool = False
    graph_ingestion_skipped: bool = False  # True when Neo4j raised an error

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

def ingest_pdf(pdf_path: str, clear_existing: bool = False) -> int:
    """
    Full ingestion pipeline for a PDF file.

    Args:
        pdf_path:       Absolute or relative path to the PDF.
        clear_existing: If True, wipe the Qdrant collection before inserting.

    Returns:
        Number of chunks indexed into Qdrant (for backward compatibility with
        IngestionService which only reads the int return value).

    Side effects:
        - Upserting chunks into Qdrant.
        - If settings.GRAPH_INGESTION_ENABLED, also extracting entities /
          relationships and upserting them into Neo4j.
    """
    result = _run_ingest(pdf_path, clear_existing=clear_existing)
    logger.info("Ingestion finished: %s", result)
    return result.chunks_indexed


def _run_ingest(pdf_path: str, clear_existing: bool = False) -> IngestResult:
    """Internal implementation — returns the full IngestResult."""
    result = IngestResult(
        graph_ingestion_enabled=settings.GRAPH_INGESTION_ENABLED
    )

    # ── 1 + 2: Parse PDF → semantic chunks ──────────────────────────────────
    logger.info("Starting ingestion for: %s", pdf_path)
    chunks = process_pdf_to_chunks(pdf_path)

    if not chunks:
        logger.warning("No chunks produced from %s — aborting ingestion", pdf_path)
        return result

    # ── 3: Embed + upsert into Qdrant ───────────────────────────────────────
    vector_store = get_vector_store()
    if clear_existing:
        logger.info("Clearing existing Qdrant collection…")
        vector_store.clear_collection()

    vector_store.add_chunks(chunks)
    result.chunks_indexed = len(chunks)
    logger.info("Qdrant: indexed %d chunks", result.chunks_indexed)

    # ── 4: Entity extraction → Neo4j ────────────────────────────────────────
    if not settings.GRAPH_INGESTION_ENABLED:
        logger.info("Graph ingestion disabled — skipping Neo4j step")
        return result

    try:
        _ingest_graph(chunks, result)
    except Exception as exc:
        logger.error(
            "Graph ingestion failed (Neo4j may be unavailable): %s — "
            "vector index is still intact",
            exc,
        )
        result.graph_ingestion_skipped = True

    return result


def _ingest_graph(chunks: list[dict], result: IngestResult) -> None:
    """Run entity/relationship extraction and upsert into Neo4j.

    Separated so that any Neo4j error can be caught cleanly in _run_ingest
    without rolling back the Qdrant write.
    """
    # Lazy import to avoid importing Neo4j driver at module load time
    from src.memory.graph_store import get_graph_store

    logger.info(
        "Starting graph extraction for %d chunks "
        "(this calls the LLM once per chunk)…",
        len(chunks),
    )

    graph_data = extract_from_chunks(chunks)

    graph_store = get_graph_store()

    # Ensure the full-text index exists before inserting (idempotent)
    graph_store.create_entity_index()

    result.entities_indexed = graph_store.add_entities(graph_data.entities)
    result.relationships_indexed = graph_store.add_relationships(
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

def ingest_chunks_from_json(json_path: str, clear_existing: bool = False) -> int:
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

    vector_store = get_vector_store()
    if clear_existing:
        vector_store.clear_collection()

    vector_store.add_chunks(chunks)
    logger.info("Ingested %d chunks from %s into Qdrant", len(chunks), json_path)

    if settings.GRAPH_INGESTION_ENABLED:
        try:
            result = IngestResult(graph_ingestion_enabled=True)
            _ingest_graph(chunks, result)
            logger.info(
                "Graph ingestion from JSON complete: %d entities, %d relationships",
                result.entities_indexed,
                result.relationships_indexed,
            )
        except Exception as exc:
            logger.error("Graph ingestion from JSON failed: %s", exc)

    return len(chunks)
