"""
Hybrid retriever — combines Qdrant vector search with Neo4j graph search.

Strategy:
1. Pull a wide candidate pool from Qdrant (dense retrieval, RETRIEVAL_RECALL_K).
2. Fuse the dense ranking with a local BM25 ranking over that pool (Reciprocal
   Rank Fusion) and keep the best TOP_K_RESULTS chunks.
3. Query Neo4j for entities/relationships matching the same query (graph retrieval)
   and append the graph context to the vector context.
"""
from __future__ import annotations

import asyncio
from typing import List, TypedDict

from backend.config import settings
from backend.retrieval.bm25 import BM25Document, BM25Index
from backend.retrieval.citation import build_citations, format_citations
from backend.retrieval.graph_store import get_graph_store
from backend.utils.helpers import get_logger
from backend.vectordb.vector_store import get_vector_store

logger = get_logger(__name__)

# Reciprocal Rank Fusion constant (standard default from the RRF paper).
RRF_K = 60


# ---------------------------------------------------------------------------
# Reranker types (previously reranker.py)
# ---------------------------------------------------------------------------

class RetrievedDocument(TypedDict):
    """Normalized retrieval result used between retrievers and the LLM."""

    content: str
    metadata: dict
    vector_rank: int


def rerank_documents(
    query: str,
    documents: list[RetrievedDocument],
    top_k: int | None = None,
) -> list[RetrievedDocument]:
    """Fuse the dense ranking with a BM25 ranking using Reciprocal Rank Fusion.

    Dense hits keep their retrieval order (`vector_rank`); BM25 is computed over
    the same candidate pool, so a chunk that matches the query lexically strongly
    can be promoted above chunks that only scored well on embedding similarity.
    """
    if not documents:
        return []

    index = BM25Index(
        BM25Document(
            content=document["content"],
            metadata=document,
            index=document["vector_rank"],
        )
        for document in documents
    )
    lexical_ranks = {
        document.metadata["vector_rank"]: rank
        for rank, (document, _score) in enumerate(index.search(query))
    }

    fused: list[tuple[float, RetrievedDocument]] = []
    for document in documents:
        dense_rank = document["vector_rank"]
        lexical_rank = lexical_ranks[dense_rank]
        score = 1.0 / (RRF_K + dense_rank + 1) + 1.0 / (RRF_K + lexical_rank + 1)
        fused.append((score, document))

    fused.sort(key=lambda item: (-item[0], item[1]["vector_rank"]))
    return [document for _score, document in fused[:top_k]]


# ---------------------------------------------------------------------------
# Hybrid search (previously hybrid_retriever.py)
# ---------------------------------------------------------------------------

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
        recall_k = max(top_k, settings.RETRIEVAL_RECALL_K)
        results = await vector_store.query(query, top_k=recall_k)
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
            # Each chunk is prefixed with its citation id so the LLM can cite [n].
            context = "\n\n---\n\n".join(
                f"[{position}] {doc['content']}"
                for position, doc in enumerate(ranked, start=1)
            )
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
    """Perform parallel Qdrant vector and Neo4j graph retrieval."""
    if top_k is None:
        top_k = settings.TOP_K_RESULTS

    vector_context, graph_context = await asyncio.gather(
        _do_vector_search(query, top_k),
        _do_graph_search(query, top_k),
    )

    parts: List[str] = []
    if vector_context:
        parts.append(vector_context)
    if graph_context:
        parts.append(graph_context)

    if not parts:
        return "No relevant information found in the handbook."

    return "\n\n".join(parts)
