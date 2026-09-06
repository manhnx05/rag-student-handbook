"""
Hybrid retriever that combines Qdrant vector search with Neo4j graph search.

Strategy:
1. Query Qdrant for semantically similar chunks (dense retrieval).
2. Query Neo4j for entities/relationships matching the same query (graph retrieval).
3. Merge and deduplicate results, prioritising vector hits, then appending
   graph context so the LLM has richer, structured knowledge.
"""
import asyncio
from typing import List

from app.vector_store.vector_store import get_vector_store
from app.knowledge_graph.graph_store import get_graph_store
from app.citation.generator import build_citations, format_citations
from app.core.config import settings
from app.core.logger import get_logger
from app.retrieval.reranker import RetrievedDocument, rerank_documents

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


async def _do_vector_search(query: str, top_k: int) -> str:
    try:
        vector_store = await get_vector_store()
        results = await vector_store.query(query, top_k=top_k)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        retrieved: list[RetrievedDocument] = [
            {
                "content": content,
                "metadata": metadata if index < len(metadatas) else {},
                "vector_rank": index,
            }
            for index, (content, metadata) in enumerate(
                zip(documents, metadatas, strict=False)
            )
        ]
        ranked = rerank_documents(query, retrieved, top_k=top_k)
        if ranked:
            context = "\n\n---\n\n".join(document["content"] for document in ranked)
            citations = format_citations(build_citations(ranked))
            return f"{context}\n\n{citations}" if citations else context
    except Exception as exc:
        logger.warning("Vector search failed: %s", exc)
    return ""

async def _do_graph_search(query: str, top_k: int) -> str:
    try:
        graph_store = await get_graph_store()
        graph_results = await graph_store.query_graph(query, top_k=top_k)
        return _format_graph_results(graph_results)
    except Exception as exc:
        logger.warning("Graph search failed: %s", exc)
    return ""

async def hybrid_search(query: str, top_k: int | None = None) -> str:
    """
    Perform hybrid retrieval combining Qdrant and Neo4j concurrently using Native Async.
    """
    if top_k is None:
        top_k = settings.TOP_K_RESULTS

    # Execute both IO-bound searches concurrently
    vector_task = _do_vector_search(query, top_k)
    graph_task = _do_graph_search(query, top_k)

    vector_context, graph_context = await asyncio.gather(vector_task, graph_task)

    parts: List[str] = []

    if vector_context:
        parts.append(vector_context)

    if graph_context:
        parts.append(graph_context)

    if not parts:
        return "No relevant information found in the handbook."

    return "\n\n".join(parts)
