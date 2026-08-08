"""
Document Loader — LLM-based entity & relationship extraction from text chunks.

Extracts structured knowledge (entities + relationships) from handbook text
chunks and returns them in a format ready for GraphStore ingestion.

Design notes:
  - Each chunk is processed individually to stay within LLM context limits.
  - Results are deduplicated by (name, type) for entities and
    (source, target, type) for relationships.
  - Failures on individual chunks are logged and skipped — they do not abort
    the entire extraction job.
  - Uses structured output (Pydantic) via JsonOutputParser for reliability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas for LLM-structured output
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    name: str = Field(description="The name of the entity")
    type: str = Field(
        description=(
            "The type of the entity. Must be one of: "
            "Person, Organization, Department, Topic, Rule, Policy, Document, Process, Entity"
        )
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional properties of the entity",
    )


class Relationship(BaseModel):
    source: str = Field(description="The name of the source entity")
    target: str = Field(description="The name of the target entity")
    type: str = Field(
        description=(
            "The relationship type (uppercase, underscores only). "
            "Must be one of: HAS_POLICY, BELONGS_TO, DEFINES, RELATED_TO, "
            "GOVERNS, REQUIRES, IMPLEMENTS"
        )
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional properties of the relationship",
    )


class ExtractionResult(BaseModel):
    entities: List[Entity] = Field(description="List of extracted entities")
    relationships: List[Relationship] = Field(
        description="List of extracted relationships"
    )


# ---------------------------------------------------------------------------
# Return type for extract_from_chunks
# ---------------------------------------------------------------------------

@dataclass
class GraphIngestionData:
    """Aggregated, deduplicated entities and relationships ready for GraphStore."""

    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    chunks_processed: int = 0
    chunks_failed: int = 0

    @property
    def total_chunks(self) -> int:
        return self.chunks_processed + self.chunks_failed


# ---------------------------------------------------------------------------
# LLM extraction helpers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert at extracting entities and relationships from Vietnamese and English academic text.
Extract all relevant entities and relationships from the given text.

Entity types: Person, Organization, Department, Topic, Rule, Policy, Document, Process, Entity.
Relationship types (uppercase): HAS_POLICY, BELONGS_TO, DEFINES, RELATED_TO, GOVERNS, REQUIRES, IMPLEMENTS.

Return ONLY valid JSON matching the schema — no markdown, no explanation.
"""

_HUMAN_PROMPT = "{text}"


def _build_chain():
    """Build the LLM extraction chain (created once per call to keep it stateless)."""
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0,
        api_key=SecretStr(settings.OPENAI_API_KEY),
    )
    prompt = ChatPromptTemplate.from_messages(
        [("system", _SYSTEM_PROMPT), ("human", _HUMAN_PROMPT)]
    )
    parser = JsonOutputParser(pydantic_object=ExtractionResult)
    return prompt | llm | parser


def extract_entities_and_relationships(text: str) -> ExtractionResult:
    """Extract entities and relationships from a single text block.

    Returns an empty ExtractionResult on failure (never raises).
    """
    chain = _build_chain()
    try:
        raw = chain.invoke({"text": text})
        return ExtractionResult(**raw)
    except Exception as exc:
        logger.warning("Entity extraction failed: %s", exc)
        return ExtractionResult(entities=[], relationships=[])


def extract_from_chunks(chunks: List[Dict[str, Any]]) -> GraphIngestionData:
    """Extract entities and relationships from a list of chunks.

    Processes each chunk independently so a single failure does not abort the
    whole run.  Results are deduplicated before being returned.

    Args:
        chunks: List of chunk dicts with at minimum a 'content' and 'id' key.

    Returns:
        GraphIngestionData with deduplicated entities and relationships.
    """
    result = GraphIngestionData()

    all_entities: List[Dict[str, Any]] = []
    all_relationships: List[Dict[str, Any]] = []

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        content = chunk.get("content", "").strip()
        chunk_id = chunk.get("id", f"chunk_{i}")

        if not content:
            logger.debug("Skipping empty chunk %s", chunk_id)
            result.chunks_failed += 1
            continue

        logger.debug("Extracting entities from chunk %d/%d (%s)…", i + 1, total, chunk_id)

        extraction = extract_entities_and_relationships(content)

        # Attach source_chunk provenance to each extracted item
        for entity in extraction.entities:
            entity_dict = entity.model_dump()
            entity_dict["properties"].setdefault("source_chunk", chunk_id)
            all_entities.append(entity_dict)

        for rel in extraction.relationships:
            rel_dict = rel.model_dump()
            rel_dict["properties"].setdefault("source_chunk", chunk_id)
            all_relationships.append(rel_dict)

        result.chunks_processed += 1

    # ── Deduplicate ──────────────────────────────────────────────────────────
    seen_entities: set[tuple] = set()
    for e in all_entities:
        key = (e["name"], e["type"])
        if key not in seen_entities:
            seen_entities.add(key)
            result.entities.append(e)

    seen_rels: set[tuple] = set()
    for r in all_relationships:
        key = (r["source"], r["target"], r["type"])
        if key not in seen_rels:
            seen_rels.add(key)
            result.relationships.append(r)

    logger.info(
        "Extraction complete: %d chunks processed, %d failed | "
        "%d unique entities, %d unique relationships",
        result.chunks_processed,
        result.chunks_failed,
        len(result.entities),
        len(result.relationships),
    )
    return result
