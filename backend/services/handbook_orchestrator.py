from collections.abc import AsyncIterator

from backend.llm.chains.rag_chain import HandbookAgent, build_agent_inputs
from backend.services.guardrails import PromptInjectionGuardrail
from backend.utils.helpers import HandbookException, extract_text_content


class HandbookOrchestrator:
    """
    Coordinates the execution of agents, tools, and memory for the Student Handbook RAG.

    The LangGraph executor is obtained lazily (async) on the first request so
    the Postgres connection pool is only opened inside a running event loop.
    """

    def __init__(self):
        self.handbook_agent = HandbookAgent()

    def process_query_stream(
        self,
        query: str,
        session_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Validate the query, then return the stream of answer chunks.

        This method is intentionally *not* an async generator: validation has to
        run when the caller invokes it, so a rejected query raises before the
        HTTP response (or any stream) has been started.
        """
        if not PromptInjectionGuardrail.check_query(query):
            raise HandbookException(
                "Query rejected: Suspicious pattern detected or query too long."
            )

        return self._stream_query(query, session_id or "default_session")

    async def _stream_query(self, query: str, session_id: str) -> AsyncIterator[str]:
        """Stream answer chunks produced by the CRAG graph."""
        # Resolve the executor lazily
        executor = await self.handbook_agent.get_executor()
        config = {"configurable": {"thread_id": session_id}}

        async for event in executor.astream_events(
            build_agent_inputs(query),
            config=config,
            version="v2",
        ):
            if event["event"] != "on_chat_model_stream":
                continue
            # Grader and rewriter nodes also call the LLM; only the answer node
            # must reach the client.
            if event.get("metadata", {}).get("langgraph_node") != "generate":
                continue

            content = extract_text_content(event["data"]["chunk"].content)
            if content:
                yield content
