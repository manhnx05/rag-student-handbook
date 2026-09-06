"""Build stable source citations from retrieved chunk metadata."""
from __future__ import annotations

from collections.abc import Iterable

from app.citation.schemas import CitationSource


def build_citations(documents: Iterable[dict]) -> list[CitationSource]:
    """Deduplicate retrieved sources by source and page."""
    citations: list[CitationSource] = []
    seen: set[tuple[str, int | None]] = set()

    for document in documents:
        metadata = document.get("metadata", {})
        source = str(metadata.get("source", "Unknown source"))
        page_value = metadata.get("page")
        page = int(page_value) if page_value is not None else None
        key = (source, page)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            CitationSource(
                id=len(citations) + 1,
                source=source,
                page=page,
                snippet=document.get("content", "")[:240].strip(),
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
