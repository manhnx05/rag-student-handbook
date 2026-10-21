"""
HandbookAgent — LangGraph CRAG agent with PostgreSQL-backed conversation memory.

Provides an advanced Agentic Workflow using Corrective RAG (CRAG) architecture:
Contextualize Query -> Retrieve -> Grade Documents -> (If relevant) -> Generate
                                                   -> (If irrelevant) -> Rewrite Query -> Retrieve
"""
from __future__ import annotations

import asyncio

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg_pool import AsyncConnectionPool

from backend.config import settings
from backend.llm.chains.base_agent import BaseAgent
from backend.llm.chains.edges import check_relevance
from backend.llm.chains.nodes import (
    contextualize_query_node,
    generate_node,
    grade_documents_node,
    retrieve_node,
    rewrite_query_node,
)
from backend.llm.chains.state import AgentState
from backend.utils.helpers import get_logger

logger = get_logger(__name__)

# Module-level singleton so the connection pool is shared across requests.
_pool: AsyncConnectionPool | None = None
_executor = None
_setup_lock = asyncio.Lock()


def build_agent_inputs(query: str) -> dict:
    """Build the initial graph state for one user turn."""
    return {
        "messages": [HumanMessage(content=query)],
        "question": query,
        "steps": [],
    }


async def _get_executor():
    """Lazily initialise the connection pool and LangGraph executor once."""
    global _pool, _executor

    if _executor is not None:
        return _executor

    async with _setup_lock:
        if _executor is not None:
            return _executor

        logger.info("Initialising PostgreSQL checkpointer for CRAG HandbookAgent …")
        _pool = AsyncConnectionPool(
            conninfo=settings.psycopg_database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"autocommit": True},
        )
        await _pool.open()

        checkpointer = AsyncPostgresSaver(conn=_pool)  # type: ignore
        await checkpointer.setup()

        # Define StateGraph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("contextualize_query", contextualize_query_node)
        workflow.add_node("retrieve", retrieve_node)
        workflow.add_node("grade_documents", grade_documents_node)
        workflow.add_node("generate", generate_node)
        workflow.add_node("rewrite_query", rewrite_query_node)

        # Build graph edges
        workflow.add_edge(START, "contextualize_query")
        workflow.add_edge("contextualize_query", "retrieve")
        workflow.add_edge("retrieve", "grade_documents")

        workflow.add_conditional_edges(
            "grade_documents",
            check_relevance,
            {
                "generate": "generate",
                "rewrite_query": "rewrite_query",
            },
        )

        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("generate", END)

        # Compile
        _executor = workflow.compile(checkpointer=checkpointer)

        logger.info("CRAG HandbookAgent executor ready with PostgreSQL checkpointer.")
        return _executor


async def close_executor() -> None:
    """Close the LangGraph postgres checkpointer connection pool."""
    global _pool, _executor
    async with _setup_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None
            _executor = None
            logger.info("CRAG HandbookAgent checkpointer pool closed.")


class HandbookAgent(BaseAgent):
    """Thin wrapper that exposes the shared LangGraph executor."""

    def get_executor(self):
        """Return the coroutine that resolves to the shared executor."""
        return _get_executor()

    async def run(self, query: str) -> str:
        executor = await self.get_executor()
        result = await executor.ainvoke(build_agent_inputs(query))
        return result["messages"][-1].content
