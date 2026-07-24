from src.agents.handbook_agent import HandbookAgent


class HandbookOrchestrator:
    """
    Coordinates the execution of agents, tools, and memory for the Student Handbook RAG.

    The LangGraph executor is obtained lazily (async) on the first request so
    the Postgres connection pool is only opened inside a running event loop.
    """

    def __init__(self):
        self.handbook_agent = HandbookAgent()

    async def process_query_stream(
        self,
        query: str,
        session_id: str | None = None,
        history: list = None,
    ):
        """
        Process a user query and yield streaming response chunks from the agent.
        """
        if session_id is None:
            session_id = "default_session"

        # Resolve the executor lazily — safe to call every time (cached after first call)
        executor = await self.handbook_agent.get_executor()

        config = {"configurable": {"thread_id": session_id}}

        # Build messages from history
        messages = []
        if history:
            for role, content in history:
                if role == "user":
                    messages.append(("user", content))
                elif role == "ai":
                    messages.append(("assistant", content))

        messages.append(("user", query))

        async for event in executor.astream_events(
            {"messages": messages},
            config=config,
            version="v2",
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield content
            elif kind == "on_tool_start":
                # Optionally surface a "searching…" indicator here in future
                pass
