from langchain_google_genai import ChatGoogleGenerativeAI
from src.core.config import settings

class LLMFactory:
    @staticmethod
    def get_llm():
        return ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            temperature=0,
            google_api_key=settings.GEMINI_API_KEY
        )
