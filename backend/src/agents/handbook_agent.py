from src.agents.base_agent import BaseAgent
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage
from src.models.llm_factory import LLMFactory
from src.tools.handbook_search_tool import handbook_search_tool

class HandbookAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.llm = LLMFactory.get_llm()
        self.tools = [handbook_search_tool]
        
        system_prompt = "Bạn là một trợ lý ảo hỗ trợ sinh viên. Nhiệm vụ của bạn là giải đáp các thắc mắc về sổ tay sinh viên, quy chế học vụ.\n\nLuôn luôn sử dụng công cụ handbook_search_tool để tìm kiếm thông tin trước khi trả lời. Dựa vào thông tin tìm được để đưa ra câu trả lời chính xác. Trả lời bằng tiếng Việt, rõ ràng và mạch lạc. Nếu thông tin không có trong sổ tay, hãy nói rằng bạn không biết."
        self.memory = MemorySaver()
        
        # Create the agent using LangGraph
        self.executor = create_react_agent(
            self.llm, 
            tools=self.tools,
            prompt=system_prompt,
            checkpointer=self.memory
        )

    async def run(self, query: str) -> str:
        result = await self.executor.ainvoke({"messages": [("user", query)]})
        return result["messages"][-1].content
    
    def get_executor(self):
        return self.executor
