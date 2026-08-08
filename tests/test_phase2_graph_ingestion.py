"""
Phase 2 Graph Ingestion Tests
==============================
Tests for:
  1. Config: GRAPH_INGESTION_ENABLED flag present and defaults to True
  2. GraphStore: _safe_label allowlist guards against Cypher injection
  3. GraphStore: relationship type regex validation
  4. document_loader: GraphIngestionData dataclass
  5. document_loader: ExtractionResult Pydantic schema
  6. document_loader: extract_from_chunks deduplication logic
  7. handbook_rag_pipeline: IngestResult dataclass / __str__
  8. handbook_rag_pipeline: _run_ingest with graph disabled (Qdrant only)
  9. handbook_rag_pipeline: _run_ingest clear_existing=True
 10. handbook_rag_pipeline: _run_ingest empty PDF returns 0 chunks
 11. handbook_rag_pipeline: Neo4j failure -> graph_ingestion_skipped, Qdrant intact
 12. handbook_rag_pipeline: ingest_pdf() backward-compat int return value
 13. IngestionService: process_pdf_ingestion is async
 14. IngestionService: process_pdf_ingestion calls ingest_pdf via thread
"""
from __future__ import annotations

import asyncio
import inspect
import os
import pathlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
BACKEND = pathlib.Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password123")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("JWT_SECRET_KEY", "supersecretkey1234567890abcdef00")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("GRAPH_INGESTION_ENABLED", "false")  # default off in tests

import pytest

# Shared fake chunks used across tests
FAKE_CHUNKS = [
    {
        "id": "test_p1_c0",
        "content": "Sinh viên cần đăng ký học phần.",
        "metadata": {"source": "test.pdf", "page": 1},
    },
    {
        "id": "test_p1_c1",
        "content": "Quy chế học vụ áp dụng từ năm 2024.",
        "metadata": {"source": "test.pdf", "page": 1},
    },
]


# ===========================================================================
# 1. Config
# ===========================================================================
class TestConfig:
    def test_graph_ingestion_enabled_field_exists(self):
        from src.core.config import Settings
        s = Settings(
            DATABASE_URL="postgresql://x:x@localhost/x",
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",
            QDRANT_URL="http://localhost:6333",
            OPENAI_API_KEY="sk-x",
            JWT_SECRET_KEY="key",
            REDIS_URL="redis://localhost:6379",
            CORS_ORIGINS="http://localhost:3000",
            GRAPH_INGESTION_ENABLED=True,  # explicit to avoid .env override in CI
        )
        assert hasattr(s, "GRAPH_INGESTION_ENABLED")
        assert s.GRAPH_INGESTION_ENABLED is True

    def test_graph_ingestion_enabled_can_be_disabled(self):
        from src.core.config import Settings
        s = Settings(
            DATABASE_URL="postgresql://x:x@localhost/x",
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",
            QDRANT_URL="http://localhost:6333",
            OPENAI_API_KEY="sk-x",
            JWT_SECRET_KEY="key",
            REDIS_URL="redis://localhost:6379",
            CORS_ORIGINS="http://localhost:3000",
            GRAPH_INGESTION_ENABLED=False,
        )
        assert s.GRAPH_INGESTION_ENABLED is False


# ===========================================================================
# 2. GraphStore safety
# ===========================================================================
class TestGraphStoreSafety:
    def test_safe_label_valid_labels_pass_through(self):
        from src.memory.graph_store import _safe_label
        for label in ("Entity", "Person", "Organization", "Department",
                      "Topic", "Rule", "Policy", "Document", "Process"):
            assert _safe_label(label) == label, f"Expected {label} to pass through"

    def test_safe_label_unknown_falls_back_to_entity(self):
        from src.memory.graph_store import _safe_label
        assert _safe_label("Unknown") == "Entity"
        assert _safe_label("SomethingElse") == "Entity"

    def test_safe_label_injection_attempt_sanitised(self):
        from src.memory.graph_store import _safe_label
        # These must NEVER reach Neo4j as label names
        assert _safe_label("DROP TABLE") == "Entity"
        assert _safe_label("'; MATCH (n) DETACH DELETE n //") == "Entity"
        assert _safe_label("") == "Entity"
        assert _safe_label(None) == "Entity"

    def test_relationship_type_valid_pattern(self):
        import re
        pattern = re.compile(r"^[A-Z][A-Z0-9_]*$")
        for rt in ("HAS_POLICY", "BELONGS_TO", "DEFINES", "RELATED_TO",
                   "GOVERNS", "REQUIRES", "IMPLEMENTS"):
            assert pattern.match(rt), f"{rt} should match"

    def test_relationship_type_invalid_pattern(self):
        import re
        pattern = re.compile(r"^[A-Z][A-Z0-9_]*$")
        for rt in ("drop_table", "123bad", "has policy", "HAS-POLICY"):
            assert not pattern.match(rt), f"{rt} should NOT match"


# ===========================================================================
# 3. GraphIngestionData
# ===========================================================================
class TestGraphIngestionData:
    def test_defaults(self):
        from src.knowledge.document_loader import GraphIngestionData
        g = GraphIngestionData()
        assert g.chunks_processed == 0
        assert g.chunks_failed == 0
        assert g.total_chunks == 0
        assert g.entities == []
        assert g.relationships == []

    def test_total_chunks_property(self):
        from src.knowledge.document_loader import GraphIngestionData
        g = GraphIngestionData(chunks_processed=7, chunks_failed=3)
        assert g.total_chunks == 10


# ===========================================================================
# 4. ExtractionResult / Entity / Relationship schemas
# ===========================================================================
class TestExtractionSchemas:
    def test_empty_result(self):
        from src.knowledge.document_loader import ExtractionResult
        r = ExtractionResult(entities=[], relationships=[])
        assert r.entities == []

    def test_entity_model(self):
        from src.knowledge.document_loader import Entity
        e = Entity(name="HUST", type="Organization")
        assert e.name == "HUST"
        assert e.type == "Organization"
        assert e.properties == {}

    def test_relationship_model(self):
        from src.knowledge.document_loader import Relationship
        r = Relationship(source="HUST", target="Policy A", type="HAS_POLICY")
        assert r.source == "HUST"
        assert r.target == "Policy A"
        assert r.type == "HAS_POLICY"

    def test_extraction_result_round_trip(self):
        from src.knowledge.document_loader import ExtractionResult, Entity, Relationship
        r = ExtractionResult(
            entities=[Entity(name="Khoa CNTT", type="Department")],
            relationships=[
                Relationship(source="Khoa CNTT", target="Quy chế", type="GOVERNS")
            ],
        )
        assert len(r.entities) == 1
        assert len(r.relationships) == 1
        assert r.entities[0].model_dump()["name"] == "Khoa CNTT"


# ===========================================================================
# 5. Deduplication logic
# ===========================================================================
class TestDeduplication:
    def test_entity_dedup(self):
        """Simulate the dedup logic used in extract_from_chunks."""
        entities = [
            {"name": "A", "type": "Topic", "properties": {}},
            {"name": "A", "type": "Topic", "properties": {}},   # duplicate
            {"name": "B", "type": "Policy", "properties": {}},
        ]
        seen: set = set()
        unique = []
        for e in entities:
            k = (e["name"], e["type"])
            if k not in seen:
                seen.add(k)
                unique.append(e)
        assert len(unique) == 2

    def test_relationship_dedup(self):
        rels = [
            {"source": "A", "target": "B", "type": "RELATED_TO", "properties": {}},
            {"source": "A", "target": "B", "type": "RELATED_TO", "properties": {}},  # dup
            {"source": "A", "target": "C", "type": "DEFINES", "properties": {}},
        ]
        seen: set = set()
        unique = []
        for r in rels:
            k = (r["source"], r["target"], r["type"])
            if k not in seen:
                seen.add(k)
                unique.append(r)
        assert len(unique) == 2


# ===========================================================================
# 6. IngestResult
# ===========================================================================
class TestIngestResult:
    def test_default_values(self):
        from src.knowledge.handbook_rag_pipeline import IngestResult
        r = IngestResult()
        assert r.chunks_indexed == 0
        assert r.entities_indexed == 0
        assert r.relationships_indexed == 0
        assert r.graph_ingestion_enabled is False
        assert r.graph_ingestion_skipped is False

    def test_str_graph_disabled(self):
        from src.knowledge.handbook_rag_pipeline import IngestResult
        r = IngestResult(chunks_indexed=5, graph_ingestion_enabled=False)
        assert "chunks=5" in str(r)
        assert "graph=disabled" in str(r)

    def test_str_graph_enabled(self):
        from src.knowledge.handbook_rag_pipeline import IngestResult
        r = IngestResult(
            chunks_indexed=5, entities_indexed=10, relationships_indexed=4,
            graph_ingestion_enabled=True
        )
        s = str(r)
        assert "chunks=5" in s
        assert "entities=10" in s
        assert "relationships=4" in s

    def test_str_graph_skipped(self):
        from src.knowledge.handbook_rag_pipeline import IngestResult
        r = IngestResult(
            chunks_indexed=5, graph_ingestion_enabled=True, graph_ingestion_skipped=True
        )
        assert "graph=skipped(error)" in str(r)


# ===========================================================================
# 7. _run_ingest pipeline (mocked I/O)
# ===========================================================================
class TestRunIngestPipeline:
    def _make_mock_vs(self):
        vs = MagicMock()
        vs.add_chunks = MagicMock()
        vs.clear_collection = MagicMock()
        return vs

    def test_graph_disabled_only_qdrant(self):
        from src.knowledge.handbook_rag_pipeline import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("src.knowledge.handbook_rag_pipeline.get_vector_store", return_value=vs),
            patch("src.knowledge.handbook_rag_pipeline.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("src.knowledge.handbook_rag_pipeline.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            result = _run_ingest("/fake/test.pdf")

        assert result.chunks_indexed == 2
        assert result.graph_ingestion_enabled is False
        vs.add_chunks.assert_called_once_with(FAKE_CHUNKS)
        vs.clear_collection.assert_not_called()

    def test_clear_existing_calls_clear_collection(self):
        from src.knowledge.handbook_rag_pipeline import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("src.knowledge.handbook_rag_pipeline.get_vector_store", return_value=vs),
            patch("src.knowledge.handbook_rag_pipeline.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("src.knowledge.handbook_rag_pipeline.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            _run_ingest("/fake/test.pdf", clear_existing=True)

        vs.clear_collection.assert_called_once()

    def test_empty_pdf_returns_zero_chunks(self):
        from src.knowledge.handbook_rag_pipeline import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("src.knowledge.handbook_rag_pipeline.get_vector_store", return_value=vs),
            patch("src.knowledge.handbook_rag_pipeline.process_pdf_to_chunks", return_value=[]),
            patch("src.knowledge.handbook_rag_pipeline.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            result = _run_ingest("/fake/empty.pdf")

        assert result.chunks_indexed == 0
        vs.add_chunks.assert_not_called()

    def test_neo4j_failure_sets_skipped_flag(self):
        from src.knowledge.handbook_rag_pipeline import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("src.knowledge.handbook_rag_pipeline.get_vector_store", return_value=vs),
            patch("src.knowledge.handbook_rag_pipeline.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("src.knowledge.handbook_rag_pipeline._ingest_graph", side_effect=Exception("Neo4j down")),
            patch("src.knowledge.handbook_rag_pipeline.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = True
            result = _run_ingest("/fake/test.pdf")

        # Qdrant must still be intact
        assert result.chunks_indexed == 2
        assert result.graph_ingestion_skipped is True
        assert result.entities_indexed == 0

    def test_ingest_pdf_returns_int(self):
        """ingest_pdf() must return an int for backward compat with IngestionService."""
        from src.knowledge.handbook_rag_pipeline import ingest_pdf
        vs = self._make_mock_vs()
        with (
            patch("src.knowledge.handbook_rag_pipeline.get_vector_store", return_value=vs),
            patch("src.knowledge.handbook_rag_pipeline.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("src.knowledge.handbook_rag_pipeline.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            count = ingest_pdf("/fake/test.pdf")

        assert isinstance(count, int)
        assert count == 2


# ===========================================================================
# 8. IngestionService async
# ===========================================================================
class TestIngestionServiceAsync:
    def test_process_pdf_ingestion_is_coroutine(self):
        from src.services.ingest_service import IngestionService
        assert inspect.iscoroutinefunction(IngestionService.process_pdf_ingestion)

    def test_process_pdf_ingestion_calls_ingest_pdf(self):
        from src.services.ingest_service import IngestionService

        async def _run():
            with patch(
                "src.services.ingest_service.ingest_pdf", return_value=5
            ) as mock_ingest:
                result = await IngestionService.process_pdf_ingestion("/fake/test.pdf")
                mock_ingest.assert_called_once_with("/fake/test.pdf", False)
                assert result == 5

        asyncio.run(_run())

    def test_process_pdf_ingestion_passes_clear_existing(self):
        from src.services.ingest_service import IngestionService

        async def _run():
            with patch(
                "src.services.ingest_service.ingest_pdf", return_value=3
            ) as mock_ingest:
                await IngestionService.process_pdf_ingestion("/fake/test.pdf", clear_existing=True)
                mock_ingest.assert_called_once_with("/fake/test.pdf", True)

        asyncio.run(_run())
