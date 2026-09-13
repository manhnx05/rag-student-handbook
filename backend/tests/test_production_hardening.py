from pathlib import Path
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.services.ingest_service import IngestionService
from app.vector_store.vector_store import VectorStore


class FakeUpload:
    def __init__(self, *chunks: bytes):
        self.chunks = list(chunks)
        self.close = AsyncMock()

    async def read(self, _size: int):
        if not self.chunks:
            return b""
        return self.chunks.pop(0)


@pytest.mark.asyncio
async def test_pdf_upload_is_streamed_and_validated(tmp_path: Path):
    upload = FakeUpload(b"%PDF-1.7\nbody")
    destination = tmp_path / "nested" / "document.pdf"

    size = await IngestionService.save_upload_file(upload, str(destination), max_size=100)

    assert size == len(b"%PDF-1.7\nbody")
    assert destination.read_bytes() == b"%PDF-1.7\nbody"
    upload.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_pdf_is_removed(tmp_path: Path):
    upload = FakeUpload(b"not-a-pdf")
    destination = tmp_path / "document.pdf"

    with pytest.raises(ValueError, match="valid PDF"):
        await IngestionService.save_upload_file(upload, str(destination), max_size=100)

    assert not destination.exists()
    upload.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_size_limit_removes_partial_file(tmp_path: Path):
    upload = FakeUpload(b"%PDF-1.7\n", b"123456")
    destination = tmp_path / "document.pdf"

    with pytest.raises(ValueError, match="maximum size"):
        await IngestionService.save_upload_file(upload, str(destination), max_size=10)

    assert not destination.exists()


def test_embedding_dimension_is_configured():
    assert settings.EMBEDDING_DIM > 0


@pytest.mark.asyncio
async def test_vector_store_uses_qdrant_uuid_for_logical_chunk_ids():
    with patch("app.vector_store.vector_store.AsyncQdrantClient"):
        store = VectorStore()

    client = MagicMock()
    client.upsert = AsyncMock()
    store.client = client
    store.collection_name = "test"

    with patch(
        "app.vector_store.vector_store.embed_texts",
        return_value=[[0.1] * settings.EMBEDDING_DIM],
    ):
        await store.add_chunks([{"id": "doc_p1_c1", "content": "text"}])

    point_id = client.upsert.call_args.kwargs["points"][0].id
    uuid.UUID(str(point_id))
