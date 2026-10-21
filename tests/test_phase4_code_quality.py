from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def _has_bare_print(source: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
        for node in ast.walk(ast.parse(source))
    )


def test_backend_package_matches_current_layout():
    expected = (
        "chunking",
        "ingestion",
        "retrieval",
        "vectordb",
        "embeddings",
        "llm/chains",
        "services",
        "api",
        "db",
        "workers",
        "prompts",
        "utils",
        "evaluation",
    )
    assert all((BACKEND_ROOT / package).is_dir() for package in expected)


def test_project_root_entrypoints_exist():
    for name in (
        "main.py",
        "requirements.txt",
        "pyproject.toml",
        "docker-compose.yml",
        "Dockerfile",
    ):
        assert (PROJECT_ROOT / name).exists(), f"Missing root file: {name}"


def test_legacy_layout_is_gone():
    assert not (PROJECT_ROOT / "src" / "main" / "python").exists()
    assert not (PROJECT_ROOT / "src" / "main" / "resources").exists()
    assert not (PROJECT_ROOT / "scripts").exists()
    assert not (PROJECT_ROOT / "notebooks").exists()


def test_next_frontend_is_removed():
    assert not (PROJECT_ROOT / "frontend" / "package.json").exists()


def test_operational_modules_do_not_use_bare_print():
    modules = (
        BACKEND_ROOT / "vectordb" / "vector_store.py",
        BACKEND_ROOT / "retrieval" / "graph_store.py",
        BACKEND_ROOT / "services" / "ingest_service.py",
        BACKEND_ROOT / "api" / "routes.py",
    )
    assert all(not _has_bare_print(path.read_text(encoding="utf-8")) for path in modules)
