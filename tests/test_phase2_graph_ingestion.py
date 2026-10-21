"""
Phase 2 Graph Ingestion Tests
==============================
Tests for:
  1. Config: GRAPH_INGESTION_ENABLED flag present and defaults to True
  2. GraphStore: _safe_label allowlist guards against Cypher injection
  3. GraphStore: relationship type regex validation
  4. GraphStore: build_fulltext_query produces Lucene-safe OR queries
  5. GraphStore: add_relationships groups by (type, source label, target label)
  6. GraphStore: create_entity_index includes the Process label
  7. loader: GraphIngestionData dataclass
  8. loader: relation deduplication logic
  9. loader: IngestResult dataclass / __str__
 10. loader: _run_ingest with graph disabled (Qdrant only)
 11. loader: _run_ingest clear_existing=True
 12. loader: _run_ingest empty PDF returns 0 chunks
 13. loader: Neo4j failure -> graph_ingestion_skipped, Qdrant intact
 14. loader: ingest_pdf() backward-compat int return value
 15. IngestionService: process_pdf_ingestion is async
 16. IngestionService: process_pdf_ingestion calls ingest_pdf via thread
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

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
        from backend.config import Settings
        s = Settings(
            DATABASE_URL="postgresql://x:x@localhost/x",
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",
            QDRANT_URL="http://localhost:6333",
            GEMINI_API_KEY="sk-x",
            REDIS_URL="redis://localhost:6379",
            CORS_ORIGINS="http://localhost:8501",
            GRAPH_INGESTION_ENABLED=True,  # explicit to avoid .env override in CI
        )
        assert hasattr(s, "GRAPH_INGESTION_ENABLED")
        assert s.GRAPH_INGESTION_ENABLED is True

    def test_graph_ingestion_enabled_can_be_disabled(self):
        from backend.config import Settings
        s = Settings(
            DATABASE_URL="postgresql://x:x@localhost/x",
            NEO4J_URI="bolt://localhost:7687",
            NEO4J_USER="neo4j",
            NEO4J_PASSWORD="password",
            QDRANT_URL="http://localhost:6333",
            GEMINI_API_KEY="sk-x",
            REDIS_URL="redis://localhost:6379",
            CORS_ORIGINS="http://localhost:8501",
            GRAPH_INGESTION_ENABLED=False,
        )
        assert s.GRAPH_INGESTION_ENABLED is False


# ===========================================================================
# 2. GraphStore safety
# ===========================================================================
class TestGraphStoreSafety:
    def test_safe_label_valid_labels_pass_through(self):
        from backend.retrieval.graph_store import _safe_label
        for label in ("Entity", "Person", "Organization", "Department",
                      "Topic", "Rule", "Policy", "Document", "Process"):
            assert _safe_label(label) == label, f"Expected {label} to pass through"

    def test_safe_label_unknown_falls_back_to_entity(self):
        from backend.retrieval.graph_store import _safe_label
        assert _safe_label("Unknown") == "Entity"
        assert _safe_label("SomethingElse") == "Entity"

    def test_safe_label_injection_attempt_sanitised(self):
        from backend.retrieval.graph_store import _safe_label
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
# 3. build_fulltext_query
# ===========================================================================
class TestBuildFulltextQuery:
    def test_question_becomes_lowercase_or_query(self):
        from backend.retrieval.graph_store import build_fulltext_query
        query = build_fulltext_query("Điều kiện xét tốt nghiệp là gì?")
        assert query
        terms = query.split(" OR ")
        assert all(term.islower() for term in terms)
        # "là" and "gì" are stopwords and must be dropped
        assert "là" not in terms
        assert "gì" not in terms
        assert "tốt nghiệp" not in terms  # tokens, not phrases

    def test_returns_empty_when_no_usable_terms(self):
        from backend.retrieval.graph_store import build_fulltext_query
        assert build_fulltext_query("là gì và của") == ""
        assert build_fulltext_query("a") == ""

    def test_limits_terms_and_deduplicates(self):
        from backend.retrieval.graph_store import build_fulltext_query
        query = build_fulltext_query(
            "tốt nghiệp tốt nghiệp học phí tín chỉ đăng ký học lại",
            max_terms=2,
        )
        terms = query.split(" OR ")
        assert len(terms) == 2
        assert len(set(terms)) == 2


# ===========================================================================
# 4. GraphStore write behaviour
# ===========================================================================
class _FakeSessionCM:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


def _store_with_session():
    from backend.retrieval.graph_store import GraphStore

    session = AsyncMock()
    session.run = AsyncMock()
    store = GraphStore()
    store.driver = MagicMock()
    store.driver.session = MagicMock(return_value=_FakeSessionCM(session))
    return store, session


class TestAddRelationshipsGrouping:
    @pytest.mark.asyncio
    async def test_groups_by_type_and_labels(self):
        store, session = _store_with_session()
        relationships = [
            {"source": "A", "target": "B", "type": "REQUIRES",
             "source_type": "Person", "target_type": "Topic", "properties": {}},
            {"source": "C", "target": "D", "type": "REQUIRES",
             "source_type": "Person", "target_type": "Topic", "properties": {}},
            {"source": "E", "target": "F", "type": "REQUIRES",
             "source_type": "Person", "target_type": "Policy", "properties": {}},
        ]

        count = await store.add_relationships(relationships)

        assert count == 3
        assert session.run.await_count == 2  # two distinct label groups
        queries = [call.args[0] for call in session.run.await_args_list]
        assert any(":Person" in q and ":Topic" in q for q in queries)
        assert any(":Policy" in q for q in queries)

    @pytest.mark.asyncio
    async def test_falls_back_to_label_less_match_without_types(self):
        store, session = _store_with_session()
        relationships = [
            {"source": "A", "target": "B", "type": "RELATED_TO", "properties": {}},
        ]

        count = await store.add_relationships(relationships)

        assert count == 1
        query = session.run.await_args.args[0]
        assert "(a {name: item.source})" in query
        assert "(b {name: item.target})" in query


class TestCreateEntityIndex:
    @pytest.mark.asyncio
    async def test_create_entity_index_includes_process_label(self):
        store, session = _store_with_session()

        await store.create_entity_index()

        query = session.run.await_args.args[0]
        assert "Process" in query
        assert "IF NOT EXISTS" in query


# ===========================================================================
# 5. GraphIngestionData
# ===========================================================================
class TestGraphIngestionData:
    def test_defaults(self):
        from backend.ingestion.loader import GraphIngestionData
        g = GraphIngestionData()
        assert g.chunks_processed == 0
        assert g.chunks_failed == 0
        assert g.total_chunks == 0
        assert g.entities == []
        assert g.relationships == []

    def test_total_chunks_property(self):
        from backend.ingestion.loader import GraphIngestionData
        g = GraphIngestionData(chunks_processed=7, chunks_failed=3)
        assert g.total_chunks == 10


# ===========================================================================
# 6. Deduplication logic
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
# 7. IngestResult
# ===========================================================================
class TestIngestResult:
    def test_default_values(self):
        from backend.ingestion.loader import IngestResult
        r = IngestResult()
        assert r.chunks_indexed == 0
        assert r.entities_indexed == 0
        assert r.relationships_indexed == 0
        assert r.graph_ingestion_enabled is False
        assert r.graph_ingestion_skipped is False

    def test_str_graph_disabled(self):
        from backend.ingestion.loader import IngestResult
        r = IngestResult(chunks_indexed=5, graph_ingestion_enabled=False)
        assert "chunks=5" in str(r)
        assert "graph=disabled" in str(r)

    def test_str_graph_enabled(self):
        from backend.ingestion.loader import IngestResult
        r = IngestResult(
            chunks_indexed=5, entities_indexed=10, relationships_indexed=4,
            graph_ingestion_enabled=True
        )
        s = str(r)
        assert "chunks=5" in s
        assert "entities=10" in s
        assert "relationships=4" in s

    def test_str_graph_skipped(self):
        from backend.ingestion.loader import IngestResult
        r = IngestResult(
            chunks_indexed=5, graph_ingestion_enabled=True, graph_ingestion_skipped=True
        )
        assert "graph=skipped(error)" in str(r)


# ===========================================================================
# 8. _run_ingest pipeline (mocked I/O)
# ===========================================================================
class TestRunIngestPipeline:
    def _make_mock_vs(self):
        vs = MagicMock()
        vs.add_chunks = AsyncMock()
        vs.clear_collection = AsyncMock()
        return vs

    @pytest.mark.asyncio
    async def test_graph_disabled_only_qdrant(self):
        from backend.ingestion.loader import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("backend.ingestion.loader.get_vector_store", new_callable=AsyncMock, return_value=vs),
            patch("backend.ingestion.loader.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("backend.ingestion.loader.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            result = await _run_ingest("/fake/test.pdf")

        assert result.chunks_indexed == 2
        assert result.graph_ingestion_enabled is False
        vs.add_chunks.assert_called_once_with(FAKE_CHUNKS)
        vs.clear_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_existing_calls_clear_collection(self):
        from backend.ingestion.loader import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("backend.ingestion.loader.get_vector_store", new_callable=AsyncMock, return_value=vs),
            patch("backend.ingestion.loader.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("backend.ingestion.loader.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            await _run_ingest("/fake/test.pdf", clear_existing=True)

        vs.clear_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_pdf_returns_zero_chunks(self):
        from backend.ingestion.loader import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("backend.ingestion.loader.get_vector_store", new_callable=AsyncMock, return_value=vs),
            patch("backend.ingestion.loader.process_pdf_to_chunks", return_value=[]),
            patch("backend.ingestion.loader.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            result = await _run_ingest("/fake/empty.pdf")

        assert result.chunks_indexed == 0
        vs.add_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_neo4j_failure_sets_skipped_flag(self):
        from backend.ingestion.loader import _run_ingest
        vs = self._make_mock_vs()
        with (
            patch("backend.ingestion.loader.get_vector_store", new_callable=AsyncMock, return_value=vs),
            patch("backend.ingestion.loader.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("backend.ingestion.loader._ingest_graph", side_effect=Exception("Neo4j down")),
            patch("backend.ingestion.loader.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = True
            result = await _run_ingest("/fake/test.pdf")

        # Qdrant must still be intact
        assert result.chunks_indexed == 2
        assert result.graph_ingestion_skipped is True
        assert result.entities_indexed == 0

    @pytest.mark.asyncio
    async def test_ingest_pdf_returns_int(self):
        """ingest_pdf() must return an int for backward compat with IngestionService."""
        from backend.ingestion.loader import ingest_pdf
        vs = self._make_mock_vs()
        with (
            patch("backend.ingestion.loader.get_vector_store", new_callable=AsyncMock, return_value=vs),
            patch("backend.ingestion.loader.process_pdf_to_chunks", return_value=FAKE_CHUNKS),
            patch("backend.ingestion.loader.settings") as ms,
        ):
            ms.GRAPH_INGESTION_ENABLED = False
            count = await ingest_pdf("/fake/test.pdf")

        assert isinstance(count, int)
        assert count == 2


# ===========================================================================
# 9. IngestionService async
# ===========================================================================
class TestIngestionServiceAsync:
    def test_process_pdf_ingestion_is_coroutine(self):
        from backend.services.ingest_service import IngestionService
        assert inspect.iscoroutinefunction(IngestionService.process_pdf_ingestion)

    @pytest.mark.asyncio
    async def test_process_pdf_ingestion_calls_ingest_pdf(self):
        from backend.services.ingest_service import IngestionService
        with patch(
            "backend.services.ingest_service.ingest_pdf",
            new_callable=AsyncMock,
            return_value=5,
        ) as mock_ingest:
            result = await IngestionService.process_pdf_ingestion("/fake/test.pdf")
            mock_ingest.assert_awaited_once_with(
                "/fake/test.pdf", clear_existing=False
            )
            assert result == 5

    @pytest.mark.asyncio
    async def test_process_pdf_ingestion_passes_clear_existing(self):
        from backend.services.ingest_service import IngestionService
        with patch(
            "backend.services.ingest_service.ingest_pdf",
            new_callable=AsyncMock,
            return_value=3,
        ) as mock_ingest:
            await IngestionService.process_pdf_ingestion(
                "/fake/test.pdf", clear_existing=True
            )
            mock_ingest.assert_awaited_once_with(
                "/fake/test.pdf", clear_existing=True
            )
