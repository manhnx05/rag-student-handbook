"""
Citation models and formatting utilities.
"""
from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class CitationSource(BaseModel):
    """A source location used to support an answer."""

    id: int = Field(ge=1)
    source: str
    page: int | None = Field(default=None, ge=1)
    snippet: str = ""


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

def build_citations(documents: Iterable[dict]) -> list[CitationSource]:
    """Number retrieved chunks so the answer prompt can reference them as [n].

    The id matches the position of the chunk in the context block, and chunks are
    only merged when they come from the exact same location *and* content, so two
    different chunks of the same page keep two distinct citations.
    """
    citations: list[CitationSource] = []
    seen: set[tuple[str, int | None, str]] = set()

    for document in documents:
        metadata = document.get("metadata", {})
        source = str(metadata.get("source", "Unknown source"))
        page_value = metadata.get("page")
        page = int(page_value) if page_value is not None else None
        snippet = document.get("content", "")[:240].strip()
        key = (source, page, snippet)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            CitationSource(
                id=len(citations) + 1,
                source=source,
                page=page,
                snippet=snippet,
            )
        )

    return citations


def format_citations(citations: Iterable[CitationSource]) -> str:
    """Format citations as a compact context block for the answer prompt."""
    lines = ["[Sources]"]
    for citation in citations:
        location = citation.source
        if citation.page is not None:
            location += f", page {citation.page}"
        lines.append(f"[{citation.id}] {location}")
    return "\n".join(lines) if len(lines) > 1 else ""
