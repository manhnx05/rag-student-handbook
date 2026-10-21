"""
GraphStore — Neo4j-backed knowledge graph for the Student Handbook RAG.

Key design decisions:
  - Uses a singleton instance (async, double-checked lock).
  - Entity type labels are validated against an allowlist to prevent
    Cypher label-injection attacks.
  - add_entities / add_relationships accept batches and return counts.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase, exceptions

from backend.config import settings
from backend.retrieval.bm25 import tokenize
from backend.utils.helpers import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Allowlist of valid Neo4j label names for entity types.
# ---------------------------------------------------------------------------
_VALID_ENTITY_LABELS: frozenset[str] = frozenset(
    {
        "Entity",
        "Person",
        "Organization",
        "Department",
        "Topic",
        "Rule",
        "Policy",
        "Document",
        "Process",
    }
)

# Lucene syntax characters that would break db.index.fulltext.queryNodes.
_LUCENE_SPECIALS = re.compile(r'[+\-!(){}\[\]^"~*?:\\/&|]')

# Very small stopword list — question words carry no entity signal.
_QUERY_STOPWORDS: frozenset[str] = frozenset(
    {
        "la", "là", "gi", "gì", "va", "và", "cua", "của", "cho", "khi", "nào",
        "the", "nao", "co", "có", "khong", "không", "duoc", "được", "thi", "thì",
        "how", "what", "when", "where", "which", "who", "why", "is", "are", "the",
        "of", "for", "and", "to", "in", "on", "a", "an", "do", "does",
    }
)


def build_fulltext_query(query: str, max_terms: int = 8) -> str:
    """Turn a natural-language question into a Lucene-safe OR query for Neo4j.

    Returns an empty string when no usable term is left, so callers can skip the
    full-text lookup instead of sending an invalid query to Neo4j.
    """
    terms: list[str] = []
    for token in tokenize(query):
        if len(token) < 2 or token in _QUERY_STOPWORDS:
            continue
        cleaned = _LUCENE_SPECIALS.sub(" ", token).strip()
        if cleaned and cleaned not in terms:
            terms.append(cleaned)

    return " OR ".join(terms[:max_terms])


def _safe_label(label: str | None) -> str:
    """Return label if it is in the allowlist, otherwise 'Entity'."""
    if not label:
        return "Entity"
    if label in _VALID_ENTITY_LABELS:
        return label
    logger.warning("Unknown entity label %r — falling back to 'Entity'", label)
    return "Entity"


class GraphStore:
    def __init__(self) -> None:
        self.uri = settings.NEO4J_URI
        self.username = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self.database = settings.NEO4J_DB
        self.driver = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
            await self.driver.verify_connectivity()
            logger.info("Connected to Neo4j at %s (db=%s)", self.uri, self.database)
        except exceptions.Neo4jError as exc:
            logger.error("Neo4j connection error: %s", exc)
            raise
        except Exception as exc:
            logger.error("Unexpected error connecting to Neo4j: %s", exc)
            raise

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()
            logger.info("Disconnected from Neo4j")

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add_entities(self, entities: List[Dict[str, Any]]) -> int:
        """Upsert entities into the graph using UNWIND for performance."""
        if not entities:
            return 0

        from collections import defaultdict

        grouped = defaultdict(list)
        for entity in entities:
            entity_name = entity.get("name")
            if not entity_name:
                continue
            label = _safe_label(entity.get("type", "Entity"))
            props = entity.get("properties", {})
            grouped[label].append({"name": entity_name, "props": props})

        count = 0
        async with self.driver.session(database=self.database) as session:
            for label, items in grouped.items():
                try:
                    await session.run(
                        f"UNWIND $items AS item "
                        f"MERGE (e:{label} {{name: item.name}}) "
                        f"SET e += item.props",
                        items=items,
                    )
                    count += len(items)
                except Exception as exc:
                    logger.error(
                        "Failed to upsert %d entities for label %s: %s",
                        len(items),
                        label,
                        exc,
                    )

        logger.info("Upserted %d / %d entities to graph", count, len(entities))
        return count

    async def add_relationships(self, relationships: List[Dict[str, Any]]) -> int:
        """Upsert relationships into the graph using UNWIND for performance.

        Batch entries are grouped by (relationship type, source label, target
        label) so a relationship is never attached to a same-named node that
        carries a different label.
        """
        if not relationships:
            return 0

        from collections import defaultdict

        grouped = defaultdict(list)
        for rel in relationships:
            source = rel.get("source")
            target = rel.get("target")
            if not source or not target:
                continue
            rel_type = rel.get("type", "RELATED_TO")
            if not re.match(r"^[A-Z][A-Z0-9_]*$", rel_type):
                rel_type = "RELATED_TO"
            props = rel.get("properties", {})
            source_label = (
                _safe_label(rel["source_type"]) if rel.get("source_type") else ""
            )
            target_label = (
                _safe_label(rel["target_type"]) if rel.get("target_type") else ""
            )
            grouped[(rel_type, source_label, target_label)].append(
                {"source": source, "target": target, "props": props}
            )

        count = 0
        async with self.driver.session(database=self.database) as session:
            for (rel_type, source_label, target_label), items in grouped.items():
                source_pattern = (
                    f"(a:{source_label} {{name: item.source}})" if source_label else "(a {name: item.source})"
                )
                target_pattern = (
                    f"(b:{target_label} {{name: item.target}})" if target_label else "(b {name: item.target})"
                )
                try:
                    await session.run(
                        f"UNWIND $items AS item "
                        f"MATCH {source_pattern}, {target_pattern} "
                        f"MERGE (a)-[r:{rel_type}]->(b) "
                        f"SET r += item.props",
                        items=items,
                    )
                    count += len(items)
                except Exception as exc:
                    logger.error(
                        "Failed to upsert %d relationships of type %s: %s",
                        len(items),
                        rel_type,
                        exc,
                    )

        logger.info(
            "Upserted %d / %d relationships to graph", count, len(relationships)
        )
        return count

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def query_graph(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Full-text search over entities, returning nodes + their neighbours."""
        fulltext_query = build_fulltext_query(query)
        if not fulltext_query:
            logger.debug("No usable full-text terms in query %r — skipping graph lookup", query)
            return []

        try:
            async with self.driver.session(database=self.database) as session:
                result = await session.run(
                    """
                    CALL db.index.fulltext.queryNodes("entityIndex", $fulltext)
                    YIELD node, score
                    OPTIONAL MATCH (node)-[r]-(neighbor)
                    RETURN node,
                           score,
                           collect(DISTINCT {relation: type(r), neighbor: neighbor.name}) AS connections
                    ORDER BY score DESC
                    LIMIT $top_k
                    """,
                    fulltext=fulltext_query,
                    top_k=top_k,
                )
                records = await result.data()
                formatted = []
                for record in records:
                    formatted.append(
                        {
                            "node": dict(record["node"]),
                            "score": record.get("score", 0),
                            "connections": record.get("connections", []),
                        }
                    )
                return formatted
        except Exception as exc:
            logger.warning("Graph query failed: %s", exc)
            return []

    async def get_stats(self) -> Dict[str, int]:
        """Return node and relationship counts."""
        async with self.driver.session(database=self.database) as session:
            node_res = await session.run("MATCH (n) RETURN count(n) AS count")
            node_record = await node_res.single()
            node_count = node_record["count"] if node_record else 0

            rel_res = await session.run("MATCH ()-[r]->() RETURN count(r) AS count")
            rel_record = await rel_res.single()
            rel_count = rel_record["count"] if rel_record else 0

        return {"node_count": node_count, "relationship_count": rel_count}

    async def clear_graph(self) -> None:
        """Delete all nodes and relationships (destructive — use with caution)."""
        async with self.driver.session(database=self.database) as session:
            await session.run("MATCH (n) DETACH DELETE n")
        logger.warning("Graph cleared — all nodes and relationships deleted")

    async def create_entity_index(self) -> None:
        """Create the full-text index used by query_graph (idempotent)."""
        async with self.driver.session(database=self.database) as session:
            try:
                await session.run(
                    "CREATE FULLTEXT INDEX entityIndex IF NOT EXISTS "
                    "FOR (n:Entity|Person|Organization|Document|Topic|Rule|Policy|Department|Process) "
                    "ON EACH [n.name]"
                )
                logger.info("Full-text index entityIndex created (or already exists)")
            except Exception as exc:
                logger.warning("Could not create entityIndex: %s", exc)


# ---------------------------------------------------------------------------
# Async singleton
# ---------------------------------------------------------------------------

_graph_store_instance: Optional[GraphStore] = None
_graph_store_lock = asyncio.Lock()


async def get_graph_store() -> GraphStore:
    """Return the process-level singleton GraphStore."""
    global _graph_store_instance
    if _graph_store_instance is None:
        async with _graph_store_lock:
            if _graph_store_instance is None:
                logger.info("Initialising GraphStore singleton…")
                _graph_store_instance = GraphStore()
                await _graph_store_instance.connect()
    return _graph_store_instance


async def reset_graph_store() -> None:
    """Replace the singleton with a fresh instance (intended for tests only)."""
    global _graph_store_instance
    async with _graph_store_lock:
        if _graph_store_instance is not None:
            try:
                await _graph_store_instance.close()
            except Exception:
                pass
            _graph_store_instance = None
