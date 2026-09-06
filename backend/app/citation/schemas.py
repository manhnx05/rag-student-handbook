"""Citation models shared by retrieval and API layers."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CitationSource(BaseModel):
    """A source location used to support an answer."""

    id: int = Field(ge=1)
    source: str
    page: int | None = Field(default=None, ge=1)
    snippet: str = ""
