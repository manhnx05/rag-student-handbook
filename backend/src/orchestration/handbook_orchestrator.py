from src.agents.handbook_agent import HandbookAgent

class HandbookOrchestrator:
    """
    Coordinates the execution of agents, tools, and memory for the Student Handbook RAG.
    """
    def __init__(self):
        self.agent = HandbookAgent()
        
    async def process_query(self, query: str, session_id: str = None):
        """
        Process a user query through the RAG pipeline and agent logic.
        This method will eventually yield streaming responses.
        """
        # TODO: Integrate with memory (session_id) and tools
        # For now, it passes the query to the agent
        response = await self.agent.run(query)
        return response
