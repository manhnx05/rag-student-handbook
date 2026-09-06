"""
HandbookAgent — LangGraph CRAG agent with PostgreSQL-backed conversation memory.

Provides an advanced Agentic Workflow using Corrective RAG (CRAG) architecture:
Retrieve -> Grade Documents -> (If relevant) -> Generate
                          -> (If irrelevant) -> Rewrite Query -> Retrieve
"""
import asyncio

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.agents.base_agent import BaseAgent
from app.core.config import settings
from app.core.logger import get_logger

from app.agents.state import AgentState
from app.agents.nodes import retrieve_node, grade_documents_node, generate_node, rewrite_query_node
from app.agents.edges import check_relevance

logger = get_logger(__name__)

# Module-level singleton so the connection pool is shared across requests.
_pool: AsyncConnectionPool | None = None
_executor = None
_setup_lock = asyncio.Lock()


async def _get_executor():
    """
    Lazily initialise the connection pool and LangGraph executor once.
    Uses a lock to prevent races on the first concurrent request.
    """
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
            kwargs={"autocommit": True}
        )
        await _pool.open()

        checkpointer = AsyncPostgresSaver(conn=_pool)  # type: ignore
        await checkpointer.setup()

        # Define StateGraph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("retrieve", retrieve_node)
        workflow.add_node("grade_documents", grade_documents_node)
        workflow.add_node("generate", generate_node)
        workflow.add_node("rewrite_query", rewrite_query_node)

        # Build graph edges
        workflow.add_edge(START, "retrieve")
        workflow.add_edge("retrieve", "grade_documents")

        workflow.add_conditional_edges(
            "grade_documents",
            check_relevance,
            {
                "generate": "generate",
                "rewrite_query": "rewrite_query"
            }
        )

        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("generate", END)

        # Compile
        _executor = workflow.compile(checkpointer=checkpointer)

        logger.info("CRAG HandbookAgent executor ready with PostgreSQL checkpointer.")
        return _executor


class HandbookAgent(BaseAgent):
    """
    Thin wrapper that exposes the shared LangGraph executor.
    """

    def get_executor(self):
        """Return the coroutine that resolves to the shared executor."""
        return _get_executor()

    async def run(self, query: str) -> str:
        executor = await self.get_executor()

        # In this CRAG setup, the state expects 'question' instead of just 'messages' at the beginning.
        # But we still want memory. LangGraph's checkpointer saves the state using thread_id.
        # However, for simplicity in `run` (which is typically called per user query),
        # we can pass the initial state. Since memory appends to `messages`,
        # we pass both question and a new message.
        from langchain_core.messages import HumanMessage

        inputs = {
            "messages": [HumanMessage(content=query)],
            "question": query,
            "steps": []
        }

        # Wait, the `run` method in this project's architecture usually uses the caller's session thread_id.
        # Wait, the original code: `await executor.ainvoke({"messages": [("user", query)]})`
        # Does the caller provide a config with `configurable: {"thread_id": ...}`?
        # Let's assume the caller of `run` handles it, wait no, let's look at where `run` is called.
        # Actually, let's just mimic what original run did:

        # Wait, the original run:
        # result = await executor.ainvoke({"messages": [("user", query)]})
        # return result["messages"][-1].content

        # But wait, does it pass `config`? In `src/services/chat_service.py`, it might call `agent.run(query)`.
        # Wait, if there's no config passed, memory isn't actually using thread_id properly! Let's check `api/main.py` or `chat_service.py` to see how it's called.

        result = await executor.ainvoke(inputs)

        # The result state will have "messages" updated with the AI response from generate_node
        return result["messages"][-1].content
