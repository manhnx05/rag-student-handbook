"""
GraphStore — Neo4j-backed knowledge graph for the Student Handbook RAG.

Key design decisions:
  - Uses a singleton instance (thread-safety addressed in Phase 3).
  - Entity type labels are validated against an allowlist to prevent
    Cypher label-injection attacks (f-string labels are a known Neo4j risk).
  - All print() calls replaced with structured logger output.
  - add_entities / add_relationships accept batches and return counts.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase, exceptions

# ... (keep other imports, maybe Neo4jGraph)
from langchain_neo4j import Neo4jGraph

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Allowlist of valid Neo4j label names for entity types.
# Anything outside this set is normalised to "Entity".
# This prevents Cypher injection via user-controlled entity type strings.
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

_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _safe_label(label: str) -> str:
    """Return label if it is in the allowlist, otherwise 'Entity'."""
    if label and label in _VALID_ENTITY_LABELS:
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
        self.graph: Optional[Neo4jGraph] = None
        # We don't connect synchronously anymore

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
            await self.driver.verify_connectivity()

            # Neo4jGraph from LangChain is synchronous, so we can't fully async it here.
            # However, for pure GraphRAG read operations, we use query_graph with direct async calls or keep Neo4jGraph.
            # Note: Neo4jGraph doesn't officially support AsyncGraphDatabase yet, so we will use self.driver directly for queries!

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
        """Upsert entities into the graph."""
        if not entities:
            return 0

        count = 0
        async with self.driver.session(database=self.database) as session:
            for entity in entities:
                entity_name = entity.get("name")
                if not entity_name:
                    continue

                label = _safe_label(entity.get("type", "Entity"))
                props = entity.get("properties", {})

                try:
                    await session.run(
                        f"MERGE (e:{label} {{name: $name}}) SET e += $props",
                        name=entity_name,
                        props=props,
                    )
                    count += 1
                except Exception as exc:
                    logger.error(
                        "Failed to upsert entity %r (%s): %s", entity_name, label, exc
                    )

        logger.info("Upserted %d / %d entities to graph", count, len(entities))
        return count

    async def add_relationships(self, relationships: List[Dict[str, Any]]) -> int:
        """Upsert relationships into the graph."""
        if not relationships:
            return 0

        count = 0
        async with self.driver.session(database=self.database) as session:
            for rel in relationships:
                source = rel.get("source")
                target = rel.get("target")
                if not source or not target:
                    continue

                rel_type = rel.get("type", "RELATED_TO")
                if not re.match(r"^[A-Z][A-Z0-9_]*$", rel_type):
                    rel_type = "RELATED_TO"

                props = rel.get("properties", {})

                try:
                    await session.run(
                        "MATCH (a {name: $source}), (b {name: $target}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) "
                        "SET r += $props",
                        source=source,
                        target=target,
                        props=props,
                    )
                    count += 1
                except Exception as exc:
                    logger.error(
                        "Failed to upsert relationship (%r)-[%s]->(%r): %s",
                        source, rel_type, target, exc,
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
        try:
            async with self.driver.session(database=self.database) as session:
                result = await session.run(
                    """
                    CALL db.index.fulltext.queryNodes("entityIndex", $query)
                    YIELD node, score
                    OPTIONAL MATCH (node)-[r]-(neighbor)
                    RETURN node,
                           score,
                           collect(DISTINCT {relation: type(r), neighbor: neighbor.name}) AS connections
                    ORDER BY score DESC
                    LIMIT $top_k
                    """,
                    query=query, top_k=top_k
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
                    "FOR (n:Entity|Person|Organization|Document|Topic|Rule|Policy|Department) "
                    "ON EACH [n.name]"
                )
                logger.info("Full-text index entityIndex created (or already exists)")
            except Exception as exc:
                logger.warning("Could not create entityIndex: %s", exc)


# ---------------------------------------------------------------------------
# Thread-safe singleton
# ---------------------------------------------------------------------------
import asyncio

_graph_store_instance: Optional[GraphStore] = None
_graph_store_lock = asyncio.Lock()


async def get_graph_store() -> GraphStore:
    """Return the process-level singleton GraphStore."""
    global _graph_store_instance
    if _graph_store_instance is None:             # fast path (no lock after init)
        async with _graph_store_lock:
            if _graph_store_instance is None:     # re-check inside lock
                logger.info("Initialising GraphStore singleton…")
                _graph_store_instance = GraphStore()
                await _graph_store_instance.connect()
    return _graph_store_instance


async def reset_graph_store() -> None:
    """Replace the singleton with a fresh instance."""
    global _graph_store_instance
    async with _graph_store_lock:
        if _graph_store_instance is not None:
            try:
                await _graph_store_instance.close()
            except Exception:
                pass
            _graph_store_instance = None
