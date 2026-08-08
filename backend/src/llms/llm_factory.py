from langchain_openai import ChatOpenAI
from src.core.config import settings

class LLMFactory:
    @staticmethod
    def get_llm():
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY
        )
