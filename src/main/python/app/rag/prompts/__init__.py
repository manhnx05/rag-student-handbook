"""Prompt templates used by the handbook RAG agent."""

from app.rag.prompts.handbook import (
    ANSWER_SYSTEM_PROMPT,
    DOCUMENT_GRADER_SYSTEM_PROMPT,
    QUERY_REWRITE_SYSTEM_PROMPT,
)

__all__ = [
    "ANSWER_SYSTEM_PROMPT",
    "DOCUMENT_GRADER_SYSTEM_PROMPT",
    "QUERY_REWRITE_SYSTEM_PROMPT",
]
