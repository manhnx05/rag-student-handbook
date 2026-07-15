from src.agents.handbook_agent import HandbookAgent
import json

class HandbookOrchestrator:
    """
    Coordinates the execution of agents, tools, and memory for the Student Handbook RAG.
    """
    def __init__(self):
        self.handbook_agent = HandbookAgent()
        self.executor = self.handbook_agent.get_executor()
        
    async def process_query_stream(self, query: str, session_id: str | None = None):
        """
        Process a user query and yield streaming responses from the agent.
        """
        if session_id is None:
            session_id = "default_session"
            
        config = {"configurable": {"thread_id": session_id}}
        
        async for event in self.executor.astream_events(
            {"messages": [("user", query)]},
            config=config,
            version="v2" # LangGraph works best with v2 events
        ):
            kind = event["event"]
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield content
            elif kind == "on_tool_start":
                # Optional: Send a specific indicator that the agent is searching
                # yield f"\n*[Searching handbook for: {event['data'].get('input')}]*\n"
                pass

