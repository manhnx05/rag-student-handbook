"""
Hybrid retriever that combines Qdrant vector search with Neo4j graph search.

Strategy:
1. Query Qdrant for semantically similar chunks (dense retrieval).
2. Query Neo4j for entities/relationships matching the same query (graph retrieval).
3. Merge and deduplicate results, prioritising vector hits, then appending
   graph context so the LLM has richer, structured knowledge.
"""
from typing import List

from src.memory.vector_store import get_vector_store
from src.memory.graph_store import get_graph_store
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


def _format_graph_results(graph_results: list) -> str:
    """Convert Neo4j graph records into a human-readable string block."""
    if not graph_results:
        return ""

    lines: List[str] = ["[Graph Knowledge]"]
    for record in graph_results:
        node = record.get("node", {})
        node_name = node.get("name", "Unknown")
        connections = record.get("connections", [])

        conn_parts = []
        for c in connections:
            if c.get("neighbor"):
                conn_parts.append(f"{c['relation']} → {c['neighbor']}")

        if conn_parts:
            lines.append(f"• {node_name}: {', '.join(conn_parts)}")
        else:
            lines.append(f"• {node_name}")

    return "\n".join(lines)


def hybrid_search(query: str, top_k: int | None = None) -> str:
    """
    Perform hybrid retrieval combining Qdrant and Neo4j.

    Returns a single string with all retrieved context ready to be passed
    into the LLM prompt.
    """
    if top_k is None:
        top_k = settings.TOP_K_RESULTS

    # ── 1. Vector search (Qdrant) ────────────────────────────────────────────
    vector_context = ""
    try:
        vector_store = get_vector_store()
        results = vector_store.query(query, top_k=top_k)
        documents = results.get("documents", [[]])[0]
        if documents:
            vector_context = "\n\n---\n\n".join(documents)
    except Exception as exc:
        logger.warning("Vector search failed: %s", exc)

    # ── 2. Graph search (Neo4j) ──────────────────────────────────────────────
    graph_context = ""
    try:
        graph_store = get_graph_store()
        graph_results = graph_store.query_graph(query, top_k=top_k)
        graph_context = _format_graph_results(graph_results)
    except Exception as exc:
        logger.warning("Graph search failed: %s", exc)

    # ── 3. Merge ─────────────────────────────────────────────────────────────
    parts: List[str] = []

    if vector_context:
        parts.append(vector_context)

    if graph_context:
        parts.append(graph_context)

    if not parts:
        return "No relevant information found in the handbook."

    return "\n\n".join(parts)
