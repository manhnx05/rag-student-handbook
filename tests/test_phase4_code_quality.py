from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "src" / "main" / "python" / "app"


def _has_bare_print(source: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
        for node in ast.walk(ast.parse(source))
    )


def test_rag_package_matches_hybrid_layout():
    expected = (
        "rag/ingestion",
        "rag/splitters",
        "rag/embeddings",
        "rag/vectorstore",
        "rag/retrievers",
        "rag/chains",
        "rag/prompts",
        "rag/knowledge_graph",
    )
    assert all((APP_ROOT / package).is_dir() for package in expected)


def test_authentication_and_next_frontend_are_removed():
    assert not (APP_ROOT / "api" / "routes" / "auth.py").exists()
    assert not (PROJECT_ROOT / "frontend").exists()


def test_operational_modules_do_not_use_bare_print():
    modules = (
        APP_ROOT / "rag" / "vectorstore" / "vector_store.py",
        APP_ROOT / "rag" / "knowledge_graph" / "graph_store.py",
        APP_ROOT / "services" / "ingest_service.py",
        APP_ROOT / "api" / "routes" / "chat.py",
    )
    assert all(not _has_bare_print(path.read_text(encoding="utf-8")) for path in modules)
