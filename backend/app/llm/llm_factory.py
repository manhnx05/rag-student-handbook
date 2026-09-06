from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

class LLMFactory:
    _instance = None

    @classmethod
    def get_llm(cls):
        if cls._instance is None:
            cls._instance = ChatGoogleGenerativeAI(
                model=settings.LLM_MODEL,
                temperature=0,
                google_api_key=settings.GEMINI_API_KEY
            )
        return cls._instance
